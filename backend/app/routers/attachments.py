from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import uuid
import logging
import mimetypes
import os
from typing import Optional

from app.database import get_db
from app.schemas.attachment import AttachmentUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/attachments", tags=["Attachments"])

# Configure upload directory
# Use environment variable if set, otherwise use /tmp/uploads on Heroku, or ./uploads locally
def get_upload_dir() -> Path:
    # Check for explicit environment variable
    if "UPLOAD_DIR" in os.environ:
        return Path(os.environ["UPLOAD_DIR"])

    # Detect Heroku environment (read-only filesystem except /tmp)
    if "DYNO" in os.environ or not os.access("/home", os.W_OK):
        return Path("/tmp/uploads")

    # Local development - use relative path
    return Path(__file__).parent.parent.parent / "uploads"

UPLOAD_DIR = get_upload_dir()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"📁 Upload directory configured: {UPLOAD_DIR}")

# Maximum file sizes (in bytes)
MAX_FILE_SIZES = {
    "image": 10 * 1024 * 1024,  # 10MB
    "video": 50 * 1024 * 1024,  # 50MB
    "audio": 25 * 1024 * 1024,  # 25MB
    "voice_note": 10 * 1024 * 1024,  # 10MB
    "file": 25 * 1024 * 1024,  # 25MB
}


def get_attachment_type(mime_type: str) -> str:
    """Determine attachment type from MIME type"""
    if mime_type.startswith("image/"):
        return "image"
    elif mime_type.startswith("video/"):
        return "video"
    elif mime_type.startswith("audio/"):
        return "audio"
    else:
        return "file"


@router.post("/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(
    file: UploadFile = File(...),
    is_voice_note: bool = Query(False),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    Upload an attachment file to local storage.

    Supports:
    - Images: PNG, JPG, GIF (max 10MB)
    - Videos: MP4, MOV (max 50MB)
    - Audio: MP3, WAV, OGG (max 25MB)
    - Voice Notes: WebM, OGG (max 10MB)
    - Documents: PDF, DOCX (max 25MB)
    """
    try:
        # Get MIME type
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

        # Determine attachment type
        attachment_type = "voice_note" if is_voice_note else get_attachment_type(mime_type)

        # Check file size
        max_size = MAX_FILE_SIZES.get(attachment_type, MAX_FILE_SIZES["file"])

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size for {attachment_type} is {max_size / (1024 * 1024):.0f}MB"
            )

        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"

        # Create type-specific subdirectory
        type_dir = UPLOAD_DIR / attachment_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = type_dir / unique_filename
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Generate URL (relative path for now)
        file_url = f"https://roamifly-admin-b97e90c67026.herokuapp.com/uploads/{attachment_type}/{unique_filename}"
        storage_path = str(file_path)

        logger.info(f"✅ Uploaded {attachment_type}: {file.filename} ({file_size} bytes) -> {file_url}")

        return AttachmentUploadResponse(
            file_url=file_url,
            file_name=file.filename,
            file_size=file_size,
            mime_type=mime_type,
            storage_path=storage_path,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.delete("/delete")
async def delete_attachment(
    file_url: str = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Delete an uploaded attachment file"""
    try:
        # Extract filename from URL
        # URL format: /uploads/{type}/{filename}
        parts = file_url.strip("/").split("/")
        if len(parts) < 3 or parts[0] != "uploads":
            raise HTTPException(status_code=400, detail="Invalid file URL")

        attachment_type = parts[1]
        filename = parts[2]

        # Construct file path
        file_path = UPLOAD_DIR / attachment_type / filename

        # Check if file exists
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Delete file
        file_path.unlink()

        logger.info(f"✅ Deleted attachment: {file_url}")

        return {"message": "Attachment deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
