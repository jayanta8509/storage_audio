from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict
import aiofiles
from pathlib import Path

app = FastAPI(title="Audio Storage API", version="1.0.0")

# Configuration
STORAGE_DIR = "audio_storage"
IMAGE_STORAGE_DIR = "image_storage"
EXPIRY_HOURS = 12
IMAGE_EXPIRY_MINUTES = 20
BASE_URL = "http://localhost:8072"  # Change this to your actual domain

# In-memory storage for file metadata (in production, use a database)
file_registry: Dict[str, dict] = {}

# Ensure storage directories exist
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(IMAGE_STORAGE_DIR, exist_ok=True)

# Mount static files to serve audio and images directly
app.mount("/static/audio", StaticFiles(directory=STORAGE_DIR), name="audio")
app.mount("/images", StaticFiles(directory=IMAGE_STORAGE_DIR), name="images")

def generate_secure_token() -> str:
    """Generate a secure unique token for file access"""
    return str(uuid.uuid4())

def get_file_extension(filename: str) -> str:
    """Extract file extension from filename"""
    return Path(filename).suffix.lower()

def get_media_type(filename: str) -> str:
    """Get the appropriate media type for audio file"""
    extension = get_file_extension(filename)
    media_types = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.aac': 'audio/aac',
        '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4',
        '.wma': 'audio/x-ms-wma'
    }
    return media_types.get(extension, 'audio/mpeg')

def is_audio_file(filename: str) -> bool:
    """Check if uploaded file is an audio file"""
    audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
    return get_file_extension(filename) in audio_extensions

def get_image_media_type(filename: str) -> str:
    """Get the appropriate media type for image file"""
    extension = get_file_extension(filename)
    media_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.tiff': 'image/tiff',
        '.ico': 'image/x-icon'
    }
    return media_types.get(extension, 'image/jpeg')

def is_image_file(filename: str) -> bool:
    """Check if uploaded file is an image file"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.ico'}
    return get_file_extension(filename) in image_extensions

def get_base_url(request: Request) -> str:
    """Automatically detect the base URL from the request"""
    # Get the scheme (http/https)
    scheme = request.url.scheme
    
    # Get the host and port
    host = request.headers.get("host", request.url.netloc)
    
    # If X-Forwarded-Proto header exists (for reverse proxies), use it
    if "x-forwarded-proto" in request.headers:
        scheme = request.headers["x-forwarded-proto"]
    
    # If X-Forwarded-Host header exists (for reverse proxies), use it
    if "x-forwarded-host" in request.headers:
        host = request.headers["x-forwarded-host"]
    
    return f"{scheme}://{host}"

async def cleanup_expired_files():
    """Background task to clean up expired files (both audio and images)"""
    while True:
        current_time = datetime.now()
        expired_tokens = []
        
        for token, file_info in file_registry.items():
            if current_time > file_info['expires_at']:
                # Delete the physical file
                file_path = file_info['file_path']
                file_type = file_info.get('file_type', 'unknown')
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted expired {file_type} file: {file_path}")
                expired_tokens.append(token)
        
        # Remove expired entries from registry
        for token in expired_tokens:
            del file_registry[token]
        
        # Check every minute for more frequent cleanup (since images expire in 20 minutes)
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    """Start the background cleanup task when the app starts"""
    asyncio.create_task(cleanup_expired_files())

@app.post("/upload-audio")
async def upload_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a binary audio file and get a secure link
    The link will be valid for 12 hours, after which the file is automatically deleted
    Domain is automatically detected from the request, or you can provide a custom domain
    """
    # Validate file type
    if not is_audio_file(file.filename):
        raise HTTPException(
            status_code=400, 
            detail="Only audio files are allowed (mp3, wav, flac, aac, ogg, m4a, wma)"
        )
    
    # Generate unique filename and secure token
    file_extension = get_file_extension(file.filename)
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(STORAGE_DIR, unique_filename)
    secure_token = generate_secure_token()
    
    try:
        # Save file to local storage
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Calculate expiry time
        expires_at = datetime.now() + timedelta(hours=EXPIRY_HOURS)
        
        # Store file metadata
        file_registry[secure_token] = {
            'original_filename': file.filename,
            'file_path': file_path,
            'unique_filename': unique_filename,
            'created_at': datetime.now(),
            'expires_at': expires_at,
        }
        
        # Generate browser-accessible audio link
        base_url = get_base_url(request)
        
        # Create a direct file access link using the unique filename
        secure_link = f"{base_url}/static/audio/{unique_filename}"
        
        return {
            "success": True,
            "message": "Audio file uploaded successfully",
            "secure_link": secure_link,
            "base_url_detected": base_url,
            "expires_at": expires_at.isoformat(),
            "file_size": len(content),
            "expires_in_hours": EXPIRY_HOURS,
        }
        
    except Exception as e:
        # Clean up file if something goes wrong
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@app.post("/upload-image")
async def upload_image(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a binary image file and get a secure link
    The link will be valid for 20 minutes, after which the file is automatically deleted
    Domain is automatically detected from the request, or you can provide a custom domain
    """
    # Validate file type
    if not is_image_file(file.filename):
        raise HTTPException(
            status_code=400, 
            detail="Only image files are allowed (jpg, jpeg, png, gif, bmp, webp, svg, tiff, ico)"
        )
    
    # Generate unique filename and secure token
    file_extension = get_file_extension(file.filename)
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(IMAGE_STORAGE_DIR, unique_filename)
    secure_token = generate_secure_token()
    
    try:
        # Save file to local storage
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Calculate expiry time (20 minutes)
        expires_at = datetime.now() + timedelta(minutes=IMAGE_EXPIRY_MINUTES)
        
        # Store file metadata
        file_registry[secure_token] = {
            'original_filename': file.filename,
            'file_path': file_path,
            'created_at': datetime.now(),
            'expires_at': expires_at,
            'file_size': len(content)
        }
        
        # Generate browser-accessible image link
        base_url = get_base_url(request)
        
        # Create a direct file access link using the unique filename
        secure_link = f"{base_url}/images/{unique_filename}"
        
        return {
            "success": True,
            "message": "Image file uploaded successfully",
            "secure_link": secure_link,
            "base_url_detected": base_url,
            "expires_at": expires_at.isoformat(),
            "expires_in_minutes": IMAGE_EXPIRY_MINUTES,
        }
        
    except Exception as e:
        # Clean up file if something goes wrong
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8072)
