import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from nylas.models.errors import NylasApiError
from nylas.models.notetakers import InviteNotetakerRequest
from nylas_client import client, NYLAS_GRANT_ID
from tasks import check_and_get_media
from database import get_media_result
from s3_uploader import s3_client, AWS_S3_BUCKET_NAME
from botocore.exceptions import ClientError
from s3_uploader import delete_folder_from_s3
from database import delete_media_result
from scheduler_service import run_scheduler_check
from nylas.models.events import CreateAutocreate, When, Conferencing, Details
from nylas.models.events import CreateEventRequest
from datetime import datetime
from contextlib import asynccontextmanager
import pytz # For handling timezones


class TranscriptionRequest(BaseModel):
    meet_url: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    print("Application startup: Starting scheduler service in the background.")
    task = asyncio.create_task(run_scheduler_check())
    yield
    print("Application shutdown: Stopping scheduler service.")
    task.cancel()

app = FastAPI(lifespan=lifespan)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    print("Application startup: Starting scheduler service in the background.")
    task = asyncio.create_task(run_scheduler_check())
    yield
    print("Application shutdown: Stopping scheduler service.")
    task.cancel()

app = FastAPI(lifespan=lifespan)


class ScheduleBotRequest(BaseModel):
    meet_url: str
    start_date: str # Format: "YYYY-MM-DD"
    start_time: str # Format: "HH:MM" (24-hour)
    timezone: str = "Asia/Kolkata"

def get_provider_from_url(url: str) -> str:
    if "zoom.us" in url:
        return "Zoom Meeting"
    elif "teams.microsoft.com" in url or "teams.live.com" in url:
        return "Microsoft Teams"
    elif "meet.google.com" in url:
        return "Google Meet"
    else:
        return "unknown"

@app.post("/schedule-bot")
async def schedule_bot_for_meeting(request: ScheduleBotRequest):
    """
    Creates a calendar event to schedule the bot to join a specific meeting at a specific time.
    The bot will stay until the meeting ends.
    """
    if not client:
        raise HTTPException(status_code=500, detail="Nylas client not initialized.")

    try:
        # 1. Convert user-provided date and time into Unix timestamps
        local_tz = pytz.timezone(request.timezone)
        start_datetime_local = local_tz.localize(datetime.strptime(f"{request.start_date} {request.start_time}", "%Y-%m-%d %H:%M"))
        start_timestamp = int(start_datetime_local.timestamp())
        
        # NEW: Set a default 1-hour duration for the calendar event placeholder
        end_timestamp = start_timestamp + 3600 # 3600 seconds = 1 hour

        # 2. Get the provider dynamically from the URL
        provider = get_provider_from_url(request.meet_url)

        # 3. Prepare the request to create a calendar event
        event_request: CreateEventRequest = {
            "calendar_id": "primary",
            "title": f"Automated Recording: {request.meet_url}",
            "when": {
                "start_time": start_timestamp,
                "end_time": end_timestamp, # Use the default end time
            },
            "conferencing": {
                "provider": provider,
                "details": {
                    "url": request.meet_url
                }
            }
        }

        # 4. Create the event using the Nylas Calendar API
        created_event_response = client.events.create(
            identifier=NYLAS_GRANT_ID,
            request_body=event_request,
            query_params={"calendar_id": "primary"}
        )
        
        event_id = created_event_response.data.id
        print(f"✅ Calendar event created with ID: {event_id} for a {provider} meeting.")

        return {
            "message": "Bot has been scheduled to join the meeting. It will stay until the meeting ends.",
            "event_id": event_id,
            "scheduled_for": start_datetime_local.isoformat()
        }

    except NylasApiError as e:
        raise HTTPException(status_code=400, detail=str(e.provider_error or e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/media/{notetaker_id}")
async def get_media_status(notetaker_id: str):
    """
    Checks the status by fetching the result from MongoDB.
    """
    db_result = await get_media_result(notetaker_id)
    
    if db_result:
        # We remove the internal MongoDB '_id' before sending the response
        db_result.pop("_id", None) 
        return db_result
    else:
        return {"status": "processing"}

# The webhook endpoint remains unchanged
@app.post("/webhook")
async def nylas_webhook(payload: dict):
    return {"status": "received"}



@app.get("/recordings")
async def list_recordings():
    """
    Lists all recordings stored in the S3 bucket.
    """
    if not AWS_S3_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="AWS S3 bucket name is not configured.")

    try:
        # List objects within the "recordings/" folder (prefix)
        response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET_NAME,
            Prefix="recordings/"
        )

        if 'Contents' not in response:
            return {"message": "No recordings found in the bucket."}

        # Create a list of recordings with their S3 URLs
        recordings_list = []
        for item in response['Contents']:
            key = item['Key']
            # Ignore the folder itself if it appears in the list
            if key == "recordings/":
                continue
            
            s3_url = f"https://{AWS_S3_BUCKET_NAME}.s3.{s3_client.meta.region_name}.amazonaws.com/{key}"
            recordings_list.append({
                "filename": key,
                "url": s3_url,
                "last_modified": item['LastModified'],
                "size_bytes": item['Size']
            })

        return {"recordings": recordings_list}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        print(f"An S3 error occurred: {error_code}")
        raise HTTPException(status_code=500, detail=f"An error occurred while accessing S3: {error_code}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
    


@app.delete("/recordings/{notetaker_id}")
async def delete_recording(notetaker_id: str):
    """
    Deletes a recording folder from S3 and its corresponding record from MongoDB.
    """
    # First, check if the record exists in the database
    db_record = await get_media_result(notetaker_id)
    if not db_record:
        raise HTTPException(status_code=404, detail="Notetaker ID not found in database.")

    try:
        # Delete the folder and all its contents from S3
        await delete_folder_from_s3(notetaker_id)

        # If S3 deletion is successful, delete the record from MongoDB
        await delete_media_result(notetaker_id)

        return {"message": f"Successfully deleted all assets for notetaker_id: {notetaker_id}"}
    
    except Exception as e:
        # If any step fails, return an error
        raise HTTPException(status_code=500, detail=f"An error occurred during deletion: {str(e)}")




