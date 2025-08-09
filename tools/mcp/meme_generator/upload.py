"""
Image upload utilities for sharing memes online.
Supports multiple free hosting services without authentication.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class MemeUploader:
    """Upload memes to free image hosting services"""

    @staticmethod
    def upload_to_0x0st(file_path: str) -> Dict[str, Any]:
        """
        Upload image to 0x0.st - a simple, no-auth file hosting service.
        Files expire based on size (365 days for <512KB, less for larger).

        Args:
            file_path: Path to the image file

        Returns:
            Dict with 'success', 'url', and optional 'error' keys
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                # Use proper user agent (0x0.st blocks certain user agents)
                headers = {"User-Agent": "curl/7.68.0"}

                with httpx.Client() as client:
                    response = client.post("https://0x0.st", files=files, headers=headers, timeout=30)

            if response.status_code == 200 and response.text:
                url = response.text.strip()
                # Check if response looks like a URL
                if url.startswith("https://0x0.st/"):
                    return {
                        "success": True,
                        "url": url,
                        "service": "0x0.st",
                        "note": "Link expires based on file size (365 days for <512KB)",
                    }
                else:
                    return {"success": False, "error": f"Unexpected response: {url}"}
            else:
                return {"success": False, "error": f"Upload failed with status {response.status_code}: {response.text}"}

        except httpx.TimeoutException:
            return {"success": False, "error": "Upload timed out after 30 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upload_to_fileio(file_path: str, expires: str = "1d") -> Dict[str, Any]:
        """
        Upload image to file.io - another free, no-auth service.

        Args:
            file_path: Path to the image file
            expires: Expiration time (1d, 1w, 2w, 1m, etc.)

        Returns:
            Dict with 'success', 'url', and optional 'error' keys
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}

                with httpx.Client() as client:
                    response = client.post(f"https://file.io/?expires={expires}", files=files, timeout=30)

            if response.status_code == 200 and response.text:
                try:
                    response_data = json.loads(response.text)
                    if response_data.get("success") and response_data.get("link"):
                        return {
                            "success": True,
                            "url": response_data["link"],
                            "service": "file.io",
                            "expires": expires,
                            "key": response_data.get("key"),
                        }
                    else:
                        return {"success": False, "error": response_data.get("message", "Upload failed")}
                except json.JSONDecodeError:
                    return {"success": False, "error": f"Invalid response: {response.text}"}
            else:
                return {"success": False, "error": f"Upload failed with status {response.status_code}: {response.text}"}

        except httpx.TimeoutException:
            return {"success": False, "error": "Upload timed out after 30 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upload(file_path: str, service: str = "auto") -> Dict[str, Any]:
        """
        Upload a meme to a hosting service.

        Args:
            file_path: Path to the image file
            service: Service to use ('0x0st', 'fileio', or 'auto' to try all)

        Returns:
            Dict with 'success', 'url', 'service', and optional 'error' keys
        """
        # Check file exists and size
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 512:  # Most free services have limits
            return {"success": False, "error": f"File too large: {file_size_mb:.1f}MB"}

        if service == "0x0st":
            return MemeUploader.upload_to_0x0st(file_path)
        elif service == "fileio":
            return MemeUploader.upload_to_fileio(file_path)
        elif service == "auto":
            # Try 0x0.st first (more reliable, longer retention)
            result = MemeUploader.upload_to_0x0st(file_path)
            if result["success"]:
                return result

            # Fallback to file.io
            logger.warning(f"0x0.st failed: {result.get('error')}, trying file.io")
            result = MemeUploader.upload_to_fileio(file_path)
            if result["success"]:
                return result

            return {"success": False, "error": "All upload services failed"}
        else:
            return {"success": False, "error": f"Unknown service: {service}"}


def upload_meme(file_path: str, service: str = "auto") -> Optional[str]:
    """
    Convenience function to upload a meme and return just the URL.

    Args:
        file_path: Path to the meme image
        service: Upload service to use

    Returns:
        URL string if successful, None if failed
    """
    result = MemeUploader.upload(file_path, service)
    if result["success"]:
        logger.info(f"Uploaded to {result.get('service')}: {result['url']}")
        return str(result["url"])  # Explicitly cast to str for mypy
    else:
        logger.error(f"Upload failed: {result.get('error')}")
        return None
