# Nylas Meeting Transcription & Recording API

A FastAPI-based application that automates meeting recording, transcription, and media processing using Nylas API. The application joins meetings as a bot, records audio/video, generates transcripts, extracts audio, captures screenshots, and stores all assets in AWS S3 with metadata in MongoDB.

## Features

- 🎥 **Automated Meeting Recording**: Join Google Meet sessions with a recording bot
- 📝 **Transcription**: Automatic transcription of meeting recordings
- 🎵 **Audio Extraction**: Extract audio from video recordings
- 📸 **Screenshot Capture**: Generate screenshots from videos at specified intervals
- ☁️ **Cloud Storage**: Upload all media assets to AWS S3
- 💾 **Database Integration**: Store metadata and transcripts in MongoDB
- 🔄 **Background Processing**: Asynchronous processing of media files
- 🗑️ **Asset Management**: Delete recordings and associated data

## Tech Stack

- **Framework**: FastAPI
- **API Integration**: Nylas API (Notetaker)
- **Cloud Storage**: AWS S3
- **Database**: MongoDB (with Motor async driver)
- **Media Processing**: 
  - MoviePy (audio extraction)
  - OpenCV (screenshot extraction)
- **Async HTTP**: HTTPX
- **Environment Management**: python-dotenv

## Prerequisites

- Python 3.13+
- Nylas API account with Notetaker access
- AWS account with S3 bucket configured
- MongoDB instance (local or cloud)
- Google Meet meeting links

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/supriyagali19/nylas.git
   cd nylas
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux/Mac
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```env
   # Nylas Configuration
   NYLAS_API_KEY=your_nylas_api_key
   NYLAS_GRANT_ID=your_nylas_grant_id

   # AWS Configuration
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_S3_BUCKET_NAME=your_bucket_name
   AWS_REGION=us-east-1

   # MongoDB Configuration
   MONGO_DETAILS=mongodb://localhost:27017
   ```

## Usage

### Start the Server

```bash
# Using uvicorn directly
uvicorn main:app --reload

# Or using the virtual environment Python
.venv\Scripts\python.exe -m uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`

### API Documentation

Once the server is running, access the interactive API documentation at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## API Endpoints

### 1. Start Recording & Transcription

**POST** `/transcribe`

Initiate a recording bot to join a meeting and start transcription.

**Request Body:**
```json
{
  "meet_url": "https://meet.google.com/xxx-xxxx-xxx"
}
```

**Response:**
```json
{
  "message": "Recording and transcription started.",
  "notetaker_id": "unique_notetaker_id"
}
```

### 2. Check Media Status

**GET** `/media/{notetaker_id}`

Check the processing status and retrieve media results.

**Response:**
```json
{
  "status": "ready",
  "meet_url": "https://meet.google.com/xxx-xxxx-xxx",
  "transcript": {
    "sentences": [...],
    "words": [...]
  },
  "s3_folder_url": "https://s3.console.aws.amazon.com/..."
}
```

Status values:
- `processing`: Media is still being processed
- `ready`: Media is ready and available
- `failed`: Processing failed

### 3. List All Recordings

**GET** `/recordings`

Retrieve a list of all recordings stored in S3.

**Response:**
```json
{
  "recordings": [
    {
      "filename": "recordings/notetaker_id/audio.mp3",
      "url": "https://bucket.s3.region.amazonaws.com/...",
      "last_modified": "2025-10-01T12:00:00Z",
      "size_bytes": 1024000
    }
  ]
}
```

### 4. Delete Recording

**DELETE** `/recordings/{notetaker_id}`

Delete all assets for a specific recording from both S3 and MongoDB.

**Response:**
```json
{
  "message": "Successfully deleted all assets for notetaker_id: xxx"
}
```

### 5. Webhook Endpoint

**POST** `/webhook`

Endpoint for receiving Nylas webhook notifications.

## Project Structure

```
nylas/
├── main.py                 # FastAPI application and route handlers
├── tasks.py                # Background tasks for media processing
├── nylas_client.py         # Nylas API client initialization
├── database.py             # MongoDB operations
├── s3_uploader.py          # AWS S3 upload/delete operations
├── video_processor.py      # Media processing (audio/screenshots)
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not in repo)
└── README.md              # This file
```

## How It Works

1. **Initiate Recording**: Send a POST request to `/transcribe` with a Google Meet URL
2. **Bot Joins Meeting**: The Nylas Notetaker bot joins the meeting
3. **Recording**: Bot records audio/video and generates transcription
4. **Background Processing**: 
   - Monitor notetaker status every 30 seconds
   - Download recording and transcript when available
   - Extract audio from video (if applicable)
   - Generate screenshots at 10-second intervals
5. **Upload to S3**: Store all processed media in organized folders
6. **Save Metadata**: Store transcript and S3 URLs in MongoDB
7. **Retrieve Results**: Query the status endpoint to get results

## Media Processing

### Audio Extraction
- Automatically detects video files
- Extracts audio track using MoviePy
- Saves as MP3 format

### Screenshot Extraction
- Captures frames at 10-second intervals
- Saves as JPEG images
- Includes timestamp in filename

## S3 Storage Structure

```
bucket-name/
└── recordings/
    └── {notetaker_id}/
        ├── audio.mp3
        ├── screenshot_0s.jpg
        ├── screenshot_10s.jpg
        ├── screenshot_20s.jpg
        └── ...
```

## MongoDB Schema

```json
{
  "_id": "notetaker_id",
  "meet_url": "https://meet.google.com/...",
  "status": "ready|processing|failed",
  "transcript": {
    "sentences": [...],
    "words": [...]
  },
  "s3_folder_url": "https://s3.console.aws.amazon.com/...",
  "error": "error message (if failed)"
}
```

## Error Handling

The application handles various error scenarios:
- Invalid meeting URLs
- Nylas API errors
- S3 upload failures
- MongoDB connection issues
- Media processing errors

## Dependencies

See `requirements.txt` for complete list:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `nylas` - Nylas API client
- `python-dotenv` - Environment variable management
- `httpx` - Async HTTP client
- `motor` - Async MongoDB driver
- `boto3` - AWS SDK
- `opencv-python-headless` - Image processing
- `moviepy` - Video processing

## Troubleshooting

### MoviePy Import Error
If you encounter `ModuleNotFoundError: No module named 'moviepy.editor'`, ensure you're using MoviePy 2.2.1+ which uses the import:
```python
from moviepy import VideoFileClip  # Correct
# NOT: from moviepy.editor import VideoFileClip  # Old version
```

### Virtual Environment Issues
Always ensure your virtual environment is activated:
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Check activation
$env:VIRTUAL_ENV  # Should show path to .venv
```

### AWS Credentials
Ensure AWS credentials have proper S3 permissions:
- `s3:PutObject`
- `s3:GetObject`
- `s3:ListBucket`
- `s3:DeleteObject`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- [Nylas API](https://www.nylas.com/) for meeting recording and transcription
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [MoviePy](https://zulko.github.io/moviepy/) for video processing

## Support

For issues and questions:
- Create an issue on GitHub
- Check Nylas API documentation: https://developer.nylas.com/

## Author

Gali Supriya - [@supriyagali19](https://github.com/supriyagali19)

---

**Note**: This application requires valid API credentials and proper configuration. Ensure all environment variables are set before running the application.
