# Audio Storage API

A FastAPI application that handles binary audio file uploads with automatic cleanup after 12 hours.

## Features

- ✅ Upload binary audio files via REST API
- ✅ Generate secure HTTPS links for file access
- ✅ Automatic file deletion after 12 hours
- ✅ Support for multiple audio formats (MP3, WAV, FLAC, AAC, OGG, M4A, WMA)
- ✅ Background cleanup process
- ✅ File metadata tracking

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Update the `BASE_URL` in `app.py` to match your domain:
```python
BASE_URL = "https://yourdomain.com"  # Change this to your actual domain
```

## Running the Server

```bash
# Development
python app.py

# Production
uvicorn app:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Upload Audio File
- **POST** `/upload-audio`
- Upload a binary audio file
- Returns a secure link valid for 12 hours

### Download Audio File
- **GET** `/audio/{token}`
- Download audio file using secure token
- File automatically deleted after expiration

### Get File Information
- **GET** `/file-info/{token}`
- Get metadata about uploaded file

### Health Check
- **GET** `/`
- API status and basic information

### Manual Cleanup
- **DELETE** `/cleanup`
- Manually trigger cleanup of expired files

## Usage Example

```bash
# Upload an audio file
curl -X POST "http://localhost:8000/upload-audio" \
     -F "file=@your-audio-file.mp3"

# Response will include a secure link like:
# https://yourdomain.com/audio/12345678-1234-1234-1234-123456789abc
```

## Security Features

- Unique tokens for each uploaded file
- File type validation (audio files only)
- Automatic cleanup after 12 hours
- No direct file path exposure

## Configuration

- **Storage Directory**: `audio_storage/` (created automatically)
- **Expiry Time**: 12 hours (configurable via `EXPIRY_HOURS`)
- **Cleanup Interval**: 5 minutes
- **Base URL**: Update in `app.py` for your domain
