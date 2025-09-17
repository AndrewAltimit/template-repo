#!/usr/bin/env python3
"""
Virtual Character Storage Service - Secure temporary file exchange.

Supports storage and transfer of:
- Audio files (TTS output, sound effects, music)
- Animation sequences and motion data
- Avatar textures and assets
- Configuration files
- Any virtual character related data

Files are automatically deleted after TTL to prevent accumulation.
Designed for cross-machine transfer (VM to host, remote servers, containers).
"""

import asyncio
import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Response for file upload."""

    file_id: str
    url: str
    expires_at: str
    size_bytes: int


class Base64UploadRequest(BaseModel):
    """Request for base64 upload."""

    audio_data: str
    filename: str = "audio.mp3"


class StorageService:
    """Secure temporary storage with automatic cleanup."""

    def __init__(self, storage_path: str = "/tmp/audio_storage", ttl_hours: float = 1.0):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self.files: Dict[str, Dict] = {}
        self.secret_key = os.getenv("STORAGE_SECRET_KEY", "")

        if not self.secret_key:
            raise ValueError("STORAGE_SECRET_KEY must be set in environment")

    def verify_token(self, token: str) -> bool:
        """Verify authentication token."""
        expected = hmac.new(self.secret_key.encode(), b"audio_storage_token", hashlib.sha256).hexdigest()
        return hmac.compare_digest(token, expected)

    def generate_file_id(self) -> str:
        """Generate secure random file ID."""
        return secrets.token_urlsafe(32)

    async def store_file(self, content: bytes, filename: str) -> Dict:
        """Store file with TTL."""
        file_id = self.generate_file_id()
        file_path = self.storage_path / file_id

        # Write file
        with open(file_path, "wb") as f:
            f.write(content)

        # Track metadata
        expires_at = datetime.now() + timedelta(seconds=self.ttl_seconds)
        self.files[file_id] = {
            "path": str(file_path),
            "filename": filename,
            "size": len(content),
            "created_at": datetime.now(),
            "expires_at": expires_at,
        }

        return {
            "file_id": file_id,
            "expires_at": expires_at.isoformat(),
            "size_bytes": len(content),
        }

    async def get_file(self, file_id: str) -> Optional[Path]:
        """Retrieve file if it exists and hasn't expired."""
        if file_id not in self.files:
            return None

        metadata = self.files[file_id]
        if datetime.now() > metadata["expires_at"]:
            # File expired, delete it
            await self.delete_file(file_id)
            return None

        file_path = Path(metadata["path"])
        if not file_path.exists():
            # File missing, clean up metadata
            del self.files[file_id]
            return None

        return file_path

    async def delete_file(self, file_id: str) -> bool:
        """Delete file and metadata."""
        if file_id not in self.files:
            return False

        metadata = self.files[file_id]
        file_path = Path(metadata["path"])

        if file_path.exists():
            file_path.unlink()

        del self.files[file_id]
        return True

    async def cleanup_expired(self):
        """Remove expired files."""
        now = datetime.now()
        expired_ids = [file_id for file_id, meta in self.files.items() if now > meta["expires_at"]]

        for file_id in expired_ids:
            await self.delete_file(file_id)

        return len(expired_ids)

    async def periodic_cleanup(self):
        """Background task to clean up expired files."""
        while True:
            try:
                count = await self.cleanup_expired()
                if count > 0:
                    print(f"Cleaned up {count} expired files")
            except Exception as e:
                print(f"Cleanup error: {e}")

            # Check every 5 minutes
            await asyncio.sleep(300)


# Initialize storage service
storage = StorageService()
app = FastAPI(title="Audio Storage Service")


def verify_auth(authorization: Optional[str] = Header(None)) -> bool:
    """Verify authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        return False

    token = authorization.replace("Bearer ", "")
    return storage.verify_token(token)


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
) -> UploadResponse:
    """Upload an audio file."""
    if not verify_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    content = await file.read()
    metadata = await storage.store_file(content, file.filename or "audio.mp3")

    # Build download URL
    base_url = os.getenv("STORAGE_BASE_URL", "http://localhost:8021")
    url = f"{base_url}/download/{metadata['file_id']}"

    return UploadResponse(
        file_id=metadata["file_id"],
        url=url,
        expires_at=metadata["expires_at"],
        size_bytes=metadata["size_bytes"],
    )


@app.post("/upload_base64")
async def upload_base64(
    request: Base64UploadRequest,
    authorization: Optional[str] = Header(None),
) -> UploadResponse:
    """Upload base64-encoded audio."""
    if not verify_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        content = base64.b64decode(request.audio_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}")

    metadata = await storage.store_file(content, request.filename)

    # Build download URL
    base_url = os.getenv("STORAGE_BASE_URL", "http://localhost:8021")
    url = f"{base_url}/download/{metadata['file_id']}"

    return UploadResponse(
        file_id=metadata["file_id"],
        url=url,
        expires_at=metadata["expires_at"],
        size_bytes=metadata["size_bytes"],
    )


@app.get("/download/{file_id}")
async def download_file(
    file_id: str,
    authorization: Optional[str] = Header(None),
):
    """Download a stored file."""
    if not verify_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    file_path = await storage.get_file(file_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found or expired")

    metadata = storage.files[file_id]
    return FileResponse(
        path=file_path,
        filename=metadata["filename"],
        media_type="audio/mpeg",
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    file_count = len(storage.files)
    return {
        "status": "healthy",
        "files_stored": file_count,
        "storage_path": str(storage.storage_path),
    }


@app.on_event("startup")
async def startup():
    """Start background cleanup task."""
    asyncio.create_task(storage.periodic_cleanup())
    print(f"Storage service started with {storage.ttl_seconds/3600:.1f} hour TTL")


if __name__ == "__main__":
    port = int(os.getenv("STORAGE_PORT", "8021"))
    host = os.getenv("STORAGE_HOST", "0.0.0.0")

    uvicorn.run(app, host=host, port=port)
