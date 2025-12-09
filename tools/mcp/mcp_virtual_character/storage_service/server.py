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
import binascii
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import hashlib
import hmac
import logging
import os
from pathlib import Path
import secrets
import time
from typing import Any, Dict, Optional, Tuple

import aiofiles  # type: ignore[import-untyped]
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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


class TokenPayload(BaseModel):
    """JWT-like token payload for authentication."""

    issued_at: float
    expires_at: float
    nonce: str


class StorageService:
    """Secure temporary storage with automatic cleanup."""

    # Token validity window (5 minutes)
    TOKEN_VALIDITY_SECONDS = 300
    # Allow clock skew of 30 seconds
    CLOCK_SKEW_SECONDS = 30

    def __init__(self, storage_path: str = "/tmp/audio_storage", ttl_hours: float = 1.0):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self.files: Dict[str, Dict[str, Any]] = {}
        self.secret_key = os.getenv("STORAGE_SECRET_KEY", "")
        # Track used nonces to prevent replay attacks (cleared periodically)
        self._used_nonces: Dict[str, float] = {}

        if not self.secret_key:
            raise ValueError("STORAGE_SECRET_KEY must be set in environment")

    def generate_token(self) -> str:
        """
        Generate a time-limited authentication token with nonce.

        Token format: base64(payload_json).signature
        This provides:
        - Time-limited validity (prevents token reuse after expiry)
        - Nonce for replay attack prevention
        - HMAC signature for integrity
        """
        now = time.time()
        payload = TokenPayload(
            issued_at=now,
            expires_at=now + self.TOKEN_VALIDITY_SECONDS,
            nonce=secrets.token_urlsafe(16),
        )

        # Encode payload
        payload_json = payload.model_dump_json()
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

        # Generate signature
        signature = hmac.new(self.secret_key.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()

        return f"{payload_b64}.{signature}"

    def verify_token(self, token: str) -> bool:
        """
        Verify authentication token with time and nonce validation.

        Returns True if:
        - Signature is valid
        - Token has not expired
        - Nonce has not been used before
        """
        try:
            # Split token into payload and signature
            parts = token.split(".")
            if len(parts) != 2:
                # Fall back to legacy simple token for backward compatibility
                return self._verify_legacy_token(token)

            payload_b64, provided_signature = parts

            # Verify signature
            expected_signature = hmac.new(self.secret_key.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()

            if not hmac.compare_digest(provided_signature, expected_signature):
                logger.warning("Token signature verification failed")
                return False

            # Decode payload
            payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
            payload = TokenPayload.model_validate_json(payload_json)

            now = time.time()

            # Check expiration (with clock skew allowance)
            if now > payload.expires_at + self.CLOCK_SKEW_SECONDS:
                logger.warning("Token expired")
                return False

            # Check not issued in the future (with clock skew allowance)
            if payload.issued_at > now + self.CLOCK_SKEW_SECONDS:
                logger.warning("Token issued in the future")
                return False

            # Check nonce hasn't been used (replay attack prevention)
            if payload.nonce in self._used_nonces:
                logger.warning("Token nonce already used (replay attack?)")
                return False

            # Mark nonce as used
            self._used_nonces[payload.nonce] = now

            return True

        except binascii.Error as e:
            logger.warning("Token base64 decode error: %s", e)
            return self._verify_legacy_token(token)
        except ValidationError as e:
            logger.warning("Token payload validation error: %s", e)
            return self._verify_legacy_token(token)
        except UnicodeDecodeError as e:
            logger.warning("Token unicode decode error: %s", e)
            return self._verify_legacy_token(token)
        except ValueError as e:
            logger.warning("Token value error: %s", e)
            return self._verify_legacy_token(token)

    def _verify_legacy_token(self, token: str) -> bool:
        """Verify legacy simple token for backward compatibility."""
        expected = hmac.new(self.secret_key.encode(), b"audio_storage_token", hashlib.sha256).hexdigest()
        return hmac.compare_digest(token, expected)

    def cleanup_used_nonces(self) -> int:
        """Remove expired nonces from tracking."""
        now = time.time()
        cutoff = now - self.TOKEN_VALIDITY_SECONDS - self.CLOCK_SKEW_SECONDS

        expired = [nonce for nonce, used_at in self._used_nonces.items() if used_at < cutoff]

        for nonce in expired:
            del self._used_nonces[nonce]

        return len(expired)

    def generate_file_id(self) -> str:
        """Generate secure random file ID."""
        return secrets.token_urlsafe(32)

    async def store_file(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Store file with TTL using async I/O."""
        file_id = self.generate_file_id()
        file_path = self.storage_path / file_id

        # Write file asynchronously
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

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

        try:
            if file_path.exists():
                file_path.unlink()
        except OSError as e:
            logger.warning("Failed to delete file %s: %s", file_path, e)

        del self.files[file_id]
        return True

    async def cleanup_expired(self) -> Tuple[int, int]:
        """Remove expired files and nonces."""
        now = datetime.now()
        expired_ids = [file_id for file_id, meta in self.files.items() if now > meta["expires_at"]]

        for file_id in expired_ids:
            await self.delete_file(file_id)

        # Also cleanup expired nonces
        nonces_cleaned = self.cleanup_used_nonces()

        return len(expired_ids), nonces_cleaned

    async def periodic_cleanup(self) -> None:
        """Background task to clean up expired files."""
        while True:
            try:
                files_cleaned, nonces_cleaned = await self.cleanup_expired()
                if files_cleaned > 0 or nonces_cleaned > 0:
                    logger.info("Cleanup: %d expired files, %d expired nonces", files_cleaned, nonces_cleaned)
            except asyncio.CancelledError:
                logger.info("Periodic cleanup cancelled")
                raise
            except OSError as e:
                logger.error("Cleanup I/O error: %s", e)

            # Check every 5 minutes
            await asyncio.sleep(300)


# Lazy initialization - storage is created on first use or startup
_storage: Optional[StorageService] = None
_cleanup_task: Optional[asyncio.Task[None]] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global _storage, _cleanup_task

    # Startup
    try:
        _storage = StorageService()
        _cleanup_task = asyncio.create_task(_storage.periodic_cleanup())
        logger.info("Storage service started with %.1f hour TTL", _storage.ttl_seconds / 3600)
        logger.info("Token validity: %d seconds", StorageService.TOKEN_VALIDITY_SECONDS)
    except ValueError as e:
        logger.error("Failed to initialize storage service: %s", e)
        logger.error("Set STORAGE_SECRET_KEY environment variable to enable storage")
        # Don't raise - allow health endpoint to report status

    yield

    # Shutdown
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
    if _storage:
        logger.info("Storage service shutting down")


app = FastAPI(title="Virtual Character Storage Service", lifespan=lifespan)


def get_storage() -> StorageService:
    """Get or create the storage service instance."""
    if _storage is None:
        raise HTTPException(
            status_code=503, detail="Storage service not initialized. Check STORAGE_SECRET_KEY environment variable."
        )
    return _storage


def verify_auth(
    authorization: Optional[str] = Header(None),
    storage: StorageService = Depends(get_storage),
) -> bool:
    """Verify authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")
    if not storage.verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return True


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    _auth: bool = Depends(verify_auth),
    storage: StorageService = Depends(get_storage),
) -> UploadResponse:
    """Upload an audio file."""
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
    _auth: bool = Depends(verify_auth),
    storage: StorageService = Depends(get_storage),
) -> UploadResponse:
    """Upload base64-encoded audio."""
    try:
        content = base64.b64decode(request.audio_data)
    except binascii.Error as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}") from e

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
    _auth: bool = Depends(verify_auth),
    storage: StorageService = Depends(get_storage),
) -> FileResponse:
    """Download a stored file."""
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
async def health() -> Dict[str, Any]:
    """Health check endpoint (no auth required)."""
    if _storage is None:
        return {
            "status": "not_initialized",
            "message": "Storage service not yet initialized",
        }

    return {
        "status": "healthy",
        "files_stored": len(_storage.files),
        "storage_path": str(_storage.storage_path),
        "nonces_tracked": len(_storage._used_nonces),
    }


@app.post("/token")
async def generate_token(
    authorization: Optional[str] = Header(None),
    storage: StorageService = Depends(get_storage),
) -> Dict[str, Any]:
    """
    Generate a new authentication token.

    Requires legacy token or valid token for authentication.
    Returns a new time-limited token with nonce.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.replace("Bearer ", "")
    if not storage.verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid token")

    new_token = storage.generate_token()
    return {
        "token": new_token,
        "expires_in_seconds": StorageService.TOKEN_VALIDITY_SECONDS,
    }


if __name__ == "__main__":
    port = int(os.getenv("STORAGE_PORT", "8021"))
    host = os.getenv("STORAGE_HOST", "0.0.0.0")

    uvicorn.run(app, host=host, port=port)
