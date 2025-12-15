"""Audio upload utilities for sharing synthesized speech online"""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Configurable upload service URLs via environment variables
UPLOAD_URL_0X0ST = os.getenv("UPLOAD_URL_0X0ST", "https://0x0.st")
UPLOAD_URL_TMPFILES = os.getenv("UPLOAD_URL_TMPFILES", "https://tmpfiles.org/api/v1/upload")
UPLOAD_URL_FILEIO = os.getenv("UPLOAD_URL_FILEIO", "https://file.io")


class AudioUploader:
    """Upload audio files to free hosting services"""

    @staticmethod
    def upload_to_0x0st(file_path: str) -> Dict[str, Any]:
        """
        Upload audio to 0x0.st - a simple, no-auth file hosting service.
        Files expire based on size (365 days for <512KB, less for larger).

        Args:
            file_path: Path to the audio file

        Returns:
            Dict with 'success', 'url', and optional 'error' keys
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                # Use proper user agent (0x0.st blocks certain user agents)
                headers = {"User-Agent": "curl/8.0.0"}

                with httpx.Client() as client:
                    response = client.post(UPLOAD_URL_0X0ST, files=files, headers=headers, timeout=30)

            if response.status_code == 200 and response.text:
                url = response.text.strip()
                # Check if response looks like a URL
                if url.startswith(f"{UPLOAD_URL_0X0ST}/") or url.startswith("https://"):
                    logger.warning("Uploading audio to public service: 0x0.st - URL will be publicly accessible")
                    return {
                        "success": True,
                        "url": url,
                        "service": "0x0.st",
                        "note": "Link expires based on file size (365 days for <512KB)",
                    }
                else:
                    return {"success": False, "error": f"Unexpected response: {url}"}
            return {
                "success": False,
                "error": f"Upload failed with status {response.status_code}: {response.text}",
            }

        except httpx.TimeoutException:
            return {"success": False, "error": "Upload timed out after 30 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _generate_tmpfiles_embed_url(url: str) -> str:
        """Generate embed URL from tmpfiles.org URL."""
        if "/tmpfiles.org/" not in url:
            return url
        parts = url.split("/")
        if len(parts) < 5:
            return url.replace("http://", "https://")
        file_id = parts[3]
        filename = parts[4] if len(parts) > 4 else "audio.mp3"
        return f"https://tmpfiles.org/dl/{file_id}/{filename}"

    @staticmethod
    def _parse_tmpfiles_response(response_text: str) -> Dict[str, Any]:
        """Parse tmpfiles.org JSON response and generate result dict."""
        response_data = json.loads(response_text)
        if not (response_data.get("status") == "success" and response_data.get("data", {}).get("url")):
            return {
                "success": False,
                "error": response_data.get("message", "Upload failed"),
            }
        url = response_data["data"]["url"]
        embed_url = AudioUploader._generate_tmpfiles_embed_url(url)
        logger.warning("Uploading audio to public service: tmpfiles.org - URL will be publicly accessible")
        return {
            "success": True,
            "url": url,
            "embed_url": embed_url,
            "service": "tmpfiles.org",
            "note": "Link expires after 1 hour of inactivity or max 30 days",
        }

    @staticmethod
    def upload_to_tmpfiles(file_path: str) -> Dict[str, Any]:
        """
        Upload audio to tmpfiles.org - reliable free hosting service.
        Files expire after 1 hour of no downloads, or max 30 days.

        Args:
            file_path: Path to the audio file

        Returns:
            Dict with 'success', 'url', 'embed_url' and optional 'error' keys
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                with httpx.Client() as client:
                    response = client.post(UPLOAD_URL_TMPFILES, files=files, timeout=30)

            if response.status_code == 403:
                return {
                    "success": False,
                    "error": "Access forbidden - service may be blocking automated uploads",
                }
            if response.status_code != 200 or not response.text:
                return {
                    "success": False,
                    "error": f"Upload failed with status {response.status_code}",
                }
            try:
                return AudioUploader._parse_tmpfiles_response(response.text)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": f"Invalid response: {response.text[:200]}",
                }
        except httpx.TimeoutException:
            return {"success": False, "error": "Upload timed out after 30 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upload_to_fileio(file_path: str, expires: str = "1d") -> Dict[str, Any]:
        """
        Upload audio to file.io - another free, no-auth service.

        Args:
            file_path: Path to the audio file
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
                    response = client.post(f"{UPLOAD_URL_FILEIO}/?expires={expires}", files=files, timeout=30)

            if response.status_code == 200 and response.text:
                try:
                    response_data = json.loads(response.text)
                    if response_data.get("success") and response_data.get("link"):
                        logger.warning("Uploading audio to public service: file.io - URL will be publicly accessible")
                        return {
                            "success": True,
                            "url": response_data["link"],
                            "service": "file.io",
                            "expires": expires,
                            "key": response_data.get("key"),
                        }
                    else:
                        return {
                            "success": False,
                            "error": response_data.get("message", "Upload failed"),
                        }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": f"Invalid response: {response.text}",
                    }
            else:
                return {
                    "success": False,
                    "error": f"Upload failed with status {response.status_code}: {response.text}",
                }

        except httpx.TimeoutException:
            return {"success": False, "error": "Upload timed out after 30 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upload(file_path: str, service: str = "auto", _preferred_format: str = "mp3") -> Dict[str, Any]:
        """
        Upload an audio file to a hosting service.

        Args:
            file_path: Path to the audio file
            service: Service to use ('tmpfiles', '0x0st', 'fileio', or 'auto' to try all)
            preferred_format: Preferred audio format for naming

        Returns:
            Dict with 'success', 'url', 'embed_url', 'service', and optional 'error' keys
        """
        # Check file exists and size
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 50:  # Audio files can be larger than images
            return {
                "success": False,
                "error": f"File too large: {file_size_mb:.1f}MB (max 50MB)",
            }

        # Log file info
        logger.info("Uploading audio file: %s (%.1fMB)", file_path, file_size_mb)

        if service == "tmpfiles":
            return AudioUploader.upload_to_tmpfiles(file_path)
        if service == "0x0st":
            return AudioUploader.upload_to_0x0st(file_path)
        if service == "fileio":
            return AudioUploader.upload_to_fileio(file_path)
        if service == "auto":
            errors = []

            # Try 0x0.st first (better retention for small files)
            if file_size_mb < 0.5:  # Under 512KB
                logger.info("Trying 0x0.st for small audio file...")
                result = AudioUploader.upload_to_0x0st(file_path)
                if result["success"]:
                    logger.info("Successfully uploaded to 0x0.st")
                    # Add embed_url for consistency
                    result["embed_url"] = result["url"]
                    return result
                errors.append(f"0x0.st: {result.get('error', 'Unknown error')}")

            # Try tmpfiles.org for medium files
            logger.info("Trying tmpfiles.org...")
            result = AudioUploader.upload_to_tmpfiles(file_path)
            if result["success"]:
                logger.info("Successfully uploaded to tmpfiles.org")
                return result
            errors.append(f"tmpfiles.org: {result.get('error', 'Unknown error')}")

            # Try file.io last
            logger.info("Trying file.io...")
            result = AudioUploader.upload_to_fileio(file_path, expires="1w")  # 1 week for audio
            if result["success"]:
                logger.info("Successfully uploaded to file.io")
                # Add embed_url for consistency
                result["embed_url"] = result["url"]
                return result
            errors.append(f"file.io: {result.get('error', 'Unknown error')}")

            # All services failed
            return {
                "success": False,
                "error": "All upload services failed",
                "details": errors,
            }
        else:
            return {
                "success": False,
                "error": f"Unknown service: {service}. Available: tmpfiles, 0x0st, fileio, auto",
            }


def upload_audio(file_path: str, service: str = "auto") -> Optional[str]:
    """
    Convenience function to upload audio and return just the URL.

    Args:
        file_path: Path to the audio file
        service: Upload service to use

    Returns:
        URL string if successful, None if failed
    """
    result = AudioUploader.upload(file_path, service)
    if result["success"]:
        logger.warning("Audio uploaded to public service %s: %s", result.get("service"), result["url"])
        logger.info("Uploaded audio to %s: %s", result.get("service"), result["url"])
        return str(result["url"])
    logger.error("Audio upload failed: %s", result.get("error"))
    return None
