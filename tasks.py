import os
import asyncio
import httpx
from nylas.models.notetakers import NotetakerState
from nylas_client import client, NYLAS_GRANT_ID
from database import save_media_result
from s3_uploader import upload_file_to_s3
from video_processor import extract_audio, extract_screenshots

async def download_json_content(url: str):
    """Asynchronously downloads and parses JSON content from a URL."""
    async with httpx.AsyncClient() as http_client:
        response = await http_client.get(url)
        response.raise_for_status()
        return response.json()

async def download_file_content(url: str):
    """Asynchronously downloads the raw binary content of a file from a URL."""
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        response = await http_client.get(url)
        response.raise_for_status()
        return response.content, response.headers.get('content-type', 'application/octet-stream')

async def check_and_get_media(notetaker_id: str, meet_url: str, was_video_requested: bool):
    """
    Checks status, processes media based on whether video was requested,
    uploads to S3, and saves all data to MongoDB.
    """
    print(f"Checking for media for notetaker: {notetaker_id}")

    while True:
        try:
            notetaker = client.notetakers.find(identifier=NYLAS_GRANT_ID, notetaker_id=notetaker_id)
            current_state = notetaker.data.state
            print(f"Notetaker state for {notetaker_id}: {current_state}")

            if current_state == NotetakerState.MEDIA_AVAILABLE:
                media_response = client.notetakers.get_media(identifier=NYLAS_GRANT_ID, notetaker_id=notetaker_id)
                
                transcript_content, s3_folder_url = None, None
                folder_name = f"recordings/{notetaker_id}"
                
                # ... (transcript processing is the same) ...
                if media_response.data.transcript and media_response.data.transcript.url:
                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.get(media_response.data.transcript.url)
                        response.raise_for_status()
                        transcript_content = response.json()

                if media_response.data.recording and media_response.data.recording.url:
                    print("Downloading recording...")
                    recording_content, content_type = await download_file_content(media_response.data.recording.url)
                    
                    # FIX: Check if video was actually requested before processing it
                    if was_video_requested and "video" in content_type:
                        print("Video processing...")
                        audio_content = await asyncio.to_thread(extract_audio, recording_content)
                        await upload_file_to_s3(audio_content, f"{folder_name}/audio.mp3", "audio/mpeg")
                        
                        screenshots = await asyncio.to_thread(extract_screenshots, recording_content)
                        for ts, img_bytes in screenshots:
                            await upload_file_to_s3(img_bytes, f"{folder_name}/screenshot_{ts}s.jpg", "image/jpeg")
                    else:
                        # Otherwise, just upload the audio directly
                        print("Audio-only file detected. Uploading directly...")
                        await upload_file_to_s3(recording_content, f"{folder_name}/audio.mp3", "audio/mpeg")
                    
                    s3_folder_url = f"https://s3.console.aws.amazon.com/s3/buckets/{os.getenv('AWS_S3_BUCKET_NAME')}?prefix={folder_name}/"

                await save_media_result(notetaker_id, meet_url, transcript_data=transcript_content, s3_folder_url=s3_folder_url)
                break

            # ... (error handling is the same) ...
            elif current_state in [NotetakerState.FAILED_ENTRY, NotetakerState.MEDIA_ERROR]:
                error_message = f"Failed with state: {current_state.value}"
                await save_media_result(notetaker_id, meet_url, error=error_message)
                break

            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"An error occurred while processing {notetaker_id}: {e}")
            await save_media_result(notetaker_id, meet_url, error="An exception occurred during polling.")
            break