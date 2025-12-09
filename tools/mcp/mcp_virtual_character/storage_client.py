#!/usr/bin/env python3
"""
Client for the audio storage service.
Handles authentication and file upload/download.
"""

import hashlib
import hmac
import os
from pathlib import Path
from typing import Dict, Optional

import requests
from requests.exceptions import RequestException


class StorageClient:
    """Client for interacting with the audio storage service."""

    def __init__(self, base_url: Optional[str] = None, secret_key: Optional[str] = None):
        """Initialize storage client."""
        # Try to load environment if not already loaded
        if not os.getenv("STORAGE_SECRET_KEY") and not secret_key:
            try:
                from .utils.env_loader import load_env_file

                load_env_file()
            except ImportError:
                pass

        self.base_url = base_url or os.getenv("STORAGE_BASE_URL", "http://localhost:8021")
        self.secret_key = secret_key or os.getenv("STORAGE_SECRET_KEY", "")

        if not self.secret_key:
            raise ValueError(
                "STORAGE_SECRET_KEY must be provided or set in environment.\n"
                "Please add STORAGE_SECRET_KEY=your_key to your .env file."
            )

    def _get_auth_token(self) -> str:
        """Generate authentication token."""
        if not self.secret_key:
            raise ValueError("STORAGE_SECRET_KEY not configured")
        return hmac.new(self.secret_key.encode(), b"audio_storage_token", hashlib.sha256).hexdigest()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {"Authorization": f"Bearer {self._get_auth_token()}"}

    def upload_file(self, file_path: str) -> Optional[str]:
        """
        Upload a file to storage and return the download URL.

        Args:
            file_path: Path to the file to upload

        Returns:
            Download URL if successful, None otherwise
        """
        path = Path(file_path)
        if not path.exists():
            print(f"Error: File not found: {file_path}")
            return None

        try:
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "audio/mpeg")}
                response = requests.post(f"{self.base_url}/upload", files=files, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                data = response.json()
                url = data.get("url")
                return url if isinstance(url, str) else None
            else:
                print(f"Upload failed: {response.status_code} - {response.text}")
                return None

        except RequestException as e:
            print(f"Upload error: {e}")
            return None

    def upload_base64(self, audio_base64: str, filename: str = "audio.mp3") -> Optional[str]:
        """
        Upload base64-encoded audio to storage.

        Args:
            audio_base64: Base64-encoded audio data
            filename: Filename for the audio

        Returns:
            Download URL if successful, None otherwise
        """
        try:
            payload = {"audio_data": audio_base64, "filename": filename}
            response = requests.post(f"{self.base_url}/upload_base64", json=payload, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                data = response.json()
                url = data.get("url")
                return url if isinstance(url, str) else None
            else:
                print(f"Upload failed: {response.status_code} - {response.text}")
                return None

        except RequestException as e:
            print(f"Upload error: {e}")
            return None

    def download_file(self, file_id: str, output_path: Optional[str] = None) -> bool:
        """
        Download a file from storage.

        Args:
            file_id: The file ID to download
            output_path: Where to save the file (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/download/{file_id}", headers=self._get_headers(), stream=True, timeout=30
            )

            if response.status_code == 200:
                # Determine output path
                if output_path:
                    path = Path(output_path)
                else:
                    # Extract filename from headers or use default
                    filename = "audio.mp3"
                    if "content-disposition" in response.headers:
                        import re

                        match = re.search(r'filename="([^"]+)"', response.headers["content-disposition"])
                        if match:
                            filename = match.group(1)
                    path = Path(filename)

                # Write file
                with open(path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"Downloaded to: {path}")
                return True
            else:
                print(f"Download failed: {response.status_code}")
                return False

        except RequestException as e:
            print(f"Download error: {e}")
            return False

    def check_health(self) -> bool:
        """Check if the storage service is healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except RequestException:
            return False


def upload_audio_and_get_url(file_path: str) -> Optional[str]:
    """
    Convenience function to upload audio and get URL.

    Args:
        file_path: Path to audio file

    Returns:
        Download URL if successful, None otherwise
    """
    client = StorageClient()
    return client.upload_file(file_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python storage_client.py <command> [args]")
        print("Commands:")
        print("  upload <file_path>     - Upload file and get URL")
        print("  download <file_id>     - Download file by ID")
        print("  health                 - Check service health")
        sys.exit(1)

    command = sys.argv[1]
    client = StorageClient()

    if command == "upload" and len(sys.argv) > 2:
        file_path = sys.argv[2]
        url = client.upload_file(file_path)
        if url:
            print(f"Upload successful! URL: {url}")
        else:
            print("Upload failed")
            sys.exit(1)

    elif command == "download" and len(sys.argv) > 2:
        file_id = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        if client.download_file(file_id, output_path):
            print("Download successful")
        else:
            print("Download failed")
            sys.exit(1)

    elif command == "health":
        if client.check_health():
            print("Service is healthy")
        else:
            print("Service is not responding")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
