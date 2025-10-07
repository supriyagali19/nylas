import asyncio
import time
from datetime import datetime, timezone
from nylas_client import client, NYLAS_GRANT_ID
from database import is_bot_invited, mark_bot_invited
from nylas.models.notetakers import InviteNotetakerRequest
# 1. Import the task we need to run
from tasks import check_and_get_media

async def run_scheduler_check():
    """
    Checks for upcoming meetings and dispatches the notetaker bot, telling the
    background task whether video was requested.
    """
    print("✅ Automated scheduler service started. Checking for meetings every 60 seconds.")
    while True:
        try:
            now = int(time.time())
            in_two_minutes = now + 120

            upcoming_events_response = client.events.list(
                identifier=NYLAS_GRANT_ID,
                query_params={"calendar_id": "primary", "start": now - 60, "end": in_two_minutes, "expand_recurring": True}
            )
            upcoming_events = upcoming_events_response.data

            for event in upcoming_events:
                if event.conferencing and event.conferencing.details and not await is_bot_invited(event.id):
                    meet_url = event.conferencing.details.get("url")
                    if not meet_url:
                        continue
                    
                    print(f"🗓️ Upcoming meeting found: '{event.title}'. Dispatching bot.")

                    # Define the settings here to be passed to the task
                    meeting_settings = {
                        "video_recording": False, # Set to False for audio-only
                        "audio_recording": True,
                        "transcription": True,
                        "diarization": True,

                    }

                    request_body: InviteNotetakerRequest = {
                        "meeting_link": meet_url,
                        "name": "Automated Bot",
                        "meeting_settings": meeting_settings,
                    }
                    notetaker_response = client.notetakers.invite(
                        identifier=NYLAS_GRANT_ID, request_body=request_body
                    )
                    notetaker_id = notetaker_response.data.id
                    print(f"🤖 Bot dispatched with notetaker_id: {notetaker_id}")

                    await mark_bot_invited(event.id, notetaker_id)

                    # FIX: Pass the video_recording setting to the background task
                    print(f"🚀 Starting status check task for {notetaker_id} (Video requested: {meeting_settings['video_recording']})")
                    asyncio.create_task(check_and_get_media(notetaker_id, meet_url, was_video_requested=meeting_settings['video_recording']))

        except Exception as e:
            print(f"❌ Error in scheduler service: {e}")

        await asyncio.sleep(60)