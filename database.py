import os
import motor.motor_asyncio
from dotenv import load_dotenv
from datetime import datetime, timezone # Import timezone

load_dotenv()

MONGO_DETAILS = os.getenv("MONGO_DETAILS")
if not MONGO_DETAILS:
    raise ValueError("Please set your MONGO_DETAILS in the .env file.")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.nylas_transcripts
transcript_collection = database.get_collection("transcripts")
scheduled_events_collection = database.get_collection("scheduled_events")

# --- Transcript and Media Functions ---

async def save_media_result(notetaker_id: str, meet_url: str, transcript_data: dict = None, s3_folder_url: str = None, error: str = None):
    """
    Saves the final processed media data, including the S3 folder URL, to MongoDB.
    """
    update_doc = {"meet_url": meet_url}
    if error:
        update_doc["status"] = "failed"
        update_doc["error"] = error
    else:
        update_doc["status"] = "ready"
        if transcript_data:
            update_doc["transcript"] = transcript_data
        if s3_folder_url:
            update_doc["s3_folder_url"] = s3_folder_url
            
    await transcript_collection.update_one(
        {"_id": notetaker_id},
        {"$set": update_doc},
        upsert=True
    )
    print(f"💾 Result for {notetaker_id} saved to MongoDB.")


async def get_media_result(notetaker_id: str):
    """
    Retrieves a result from MongoDB.
    """
    return await transcript_collection.find_one({"_id": notetaker_id})

async def delete_media_result(notetaker_id: str):
    """
    Deletes a transcription result from MongoDB.
    """
    delete_result = await transcript_collection.delete_one({"_id": notetaker_id})
    if delete_result.deleted_count > 0:
        print(f"💾 Record for {notetaker_id} deleted from MongoDB.")
    return delete_result


# --- Scheduled Event Tracking Functions ---

async def is_bot_invited(event_id: str) -> bool:
    """Checks if a bot has already been invited for a given event ID."""
    document = await scheduled_events_collection.find_one({"_id": event_id})
    return document is not None

async def mark_bot_invited(event_id: str, notetaker_id: str):
    """Marks that a bot has been invited for an event to prevent duplicate invites."""
    await scheduled_events_collection.insert_one({
        "_id": event_id,
        "notetaker_id": notetaker_id,
        # FIX: Replaced datetime.utcnow() with the modern equivalent
        "invited_at": datetime.now(timezone.utc)
    })