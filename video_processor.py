import cv2
import os
import tempfile
from moviepy import VideoFileClip

def extract_audio(video_content: bytes) -> bytes:
    """
    Extracts the audio from video content.

    Args:
        video_content: The binary content of the video file.

    Returns:
        The binary content of the extracted audio file (as mp3).
    """
    # Use a temporary file to process the video
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
        temp_video_file.write(video_content)
        video_path = temp_video_file.name

    try:
        video_clip = VideoFileClip(video_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
            audio_path = temp_audio_file.name
        
        video_clip.audio.write_audiofile(audio_path)
        video_clip.close()
        
        with open(audio_path, "rb") as f:
            audio_content = f.read()

        # Clean up temporary files
        os.remove(audio_path)
        return audio_content
    finally:
        os.remove(video_path)


def extract_screenshots(video_content: bytes, interval_seconds: int = 10) -> list:
    """
    Extracts screenshots from a video at a specified interval.

    Args:
        video_content: The binary content of the video file.
        interval_seconds: The interval in seconds between screenshots.

    Returns:
        A list of tuples, where each tuple contains the screenshot's timestamp (in seconds)
        and its binary content (as JPEG).
    """
    screenshots = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
        temp_video_file.write(video_content)
        video_path = temp_video_file.name
    
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * interval_seconds)
        
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                timestamp_sec = int(frame_count / fps)
                is_success, buffer = cv2.imencode(".jpg", frame)
                if is_success:
                    screenshots.append((timestamp_sec, buffer.tobytes()))
            
            frame_count += 1
            
        cap.release()
        return screenshots
    finally:
        os.remove(video_path)