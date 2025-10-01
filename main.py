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

app = FastAPI()

class TranscriptionRequest(BaseModel):
    meet_url: str

@app.post("/transcribe")
async def transcribe_meeting(
    request: TranscriptionRequest, background_tasks: BackgroundTasks
):
    # This function remains exactly the same
    if not client:
        raise HTTPException(status_code=500, detail="Nylas client not initialized.")

    request_body: InviteNotetakerRequest = {
        "meeting_link": request.meet_url,
        "name": "Recording & Transcription Bot",
        "meeting_settings": {
            "video_recording": True,
            "audio_recording": True,
            "transcription": True,
        },
    }

    try:
        notetaker_response = client.notetakers.invite(
            identifier=NYLAS_GRANT_ID, request_body=request_body
        )
        notetaker_id = notetaker_response.data.id
        background_tasks.add_task(check_and_get_media, notetaker_id, request.meet_url)
        return {
            "message": "Recording and transcription started.",
            "notetaker_id": notetaker_id,
        }
    except NylasApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

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




