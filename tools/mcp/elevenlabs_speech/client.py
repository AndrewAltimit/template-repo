"""ElevenLabs API client wrapper"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import websockets

from .models.synthesis_config import StreamConfig, SynthesisConfig, SynthesisResult
from .models.voice_settings import VoiceModel

logger = logging.getLogger(__name__)


class ElevenLabsClient:
    """Client for ElevenLabs API interactions"""

    BASE_URL = "https://api.elevenlabs.io/v1"
    WS_URL = "wss://api.elevenlabs.io/v1/text-to-speech"

    def __init__(self, api_key: Optional[str] = None, project_root: Optional[Path] = None, output_dir: Optional[Path] = None):
        """
        Initialize ElevenLabs client

        Args:
            api_key: ElevenLabs API key (or from environment)
            project_root: Optional project root directory for outputs
            output_dir: Optional specific output directory to use
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.warning("No ElevenLabs API key provided")

        self.headers = {"xi-api-key": self.api_key or "", "Content-Type": "application/json"}

        # Store project root and output directory
        self.project_root = project_root or Path.cwd()
        self.output_dir = output_dir or self.project_root / "outputs" / "elevenlabs_speech"

        # Create HTTP client
        self.client = httpx.AsyncClient(headers=self.headers, timeout=httpx.Timeout(60.0))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def synthesize_speech(self, config: SynthesisConfig) -> SynthesisResult:
        """
        Synthesize speech from text

        Args:
            config: Synthesis configuration

        Returns:
            SynthesisResult with audio data or URL
        """
        try:
            # Prepare API parameters
            api_params = config.to_api_params()

            # Store the original text for metadata
            original_text = config.text

            # Make API request
            url = f"{self.BASE_URL}/text-to-speech/{config.voice_id}"

            # Add output format to URL if streaming
            if config.stream:
                url += f"/stream?output_format={config.output_format.value}"

            try:
                response = await self.client.post(
                    url,
                    json={
                        "text": api_params["text"],
                        "model_id": api_params["model_id"],
                        "voice_settings": api_params["voice_settings"],
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Log safe error without exposing headers/API key
                logger.error(f"ElevenLabs API error: {e.response.status_code} - Voice: {config.voice_id}")
                return SynthesisResult(
                    success=False,
                    error=f"API request failed with status {e.response.status_code}",
                    character_count=len(config.text),
                )
            except httpx.RequestError as e:
                # Log connection error without exposing sensitive data
                logger.error(f"Connection error to ElevenLabs API: {type(e).__name__}")
                return SynthesisResult(
                    success=False, error="Failed to connect to ElevenLabs API", character_count=len(config.text)
                )

            if response.status_code == 200:
                audio_data = response.content

                # Prepare comprehensive metadata
                synthesis_metadata = {
                    "original_text": original_text,
                    "processed_text": api_params["text"],
                    "text_length": len(api_params["text"]),
                    "model": api_params["model_id"],
                    "voice_id": config.voice_id,
                    "voice_settings": api_params["voice_settings"],
                    "format": config.output_format.value,
                    "streaming": config.stream,
                    "language_code": config.language_code,
                }

                # Save to local file with metadata
                local_path = await self._save_audio(audio_data, config.output_format.value, metadata=synthesis_metadata)

                return SynthesisResult(
                    success=True,
                    audio_data=audio_data,
                    local_path=local_path,
                    character_count=len(config.text),
                    model_used=config.model.value,
                    voice_id=config.voice_id,
                    metadata=synthesis_metadata,
                )
            else:
                error_msg = f"API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return SynthesisResult(success=False, error=error_msg, character_count=len(config.text))

        except Exception as e:
            # Log safe error without exposing sensitive information
            logger.error(f"Synthesis error: {type(e).__name__}")
            return SynthesisResult(
                success=False, error=f"Synthesis failed: {type(e).__name__}", character_count=len(config.text)
            )

    async def synthesize_with_websocket(self, config: StreamConfig) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesis using WebSocket

        Args:
            config: Stream configuration

        Yields:
            Audio data chunks
        """
        ws_params = config.to_websocket_params()

        # Build WebSocket URL
        ws_url = f"{self.WS_URL}/{config.voice_id}/stream-input?model_id={config.model.value}"

        async with websockets.connect(ws_url, extra_headers={"xi-api-key": self.api_key}) as websocket:

            # Send initial configuration
            await websocket.send(
                json.dumps(
                    {
                        "text": " ",  # Initial empty text to establish connection
                        "voice_settings": ws_params["voice_settings"],
                        "chunk_length_schedule": ws_params["chunk_length_schedule"],
                    }
                )
            )

            # Send text in chunks
            text_chunks = self._chunk_text(config.text, ws_params["chunk_length_schedule"])

            for i, chunk in enumerate(text_chunks):
                is_last = i == len(text_chunks) - 1

                message = {"text": chunk, "flush": is_last or config.auto_flush}

                await websocket.send(json.dumps(message))

                # Receive audio data
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                        if isinstance(data, bytes):
                            yield data
                        else:
                            # Parse JSON response for metadata
                            response = json.loads(data)
                            if response.get("audio"):
                                yield response["audio"]
                            if response.get("done"):
                                break
                    except asyncio.TimeoutError:
                        if is_last:
                            break
                        continue

    async def generate_sound_effect(self, prompt: str, duration_seconds: float = 5.0) -> SynthesisResult:
        """
        Generate sound effect from text prompt

        Args:
            prompt: Description of the sound effect
            duration_seconds: Duration (max 22 seconds)

        Returns:
            SynthesisResult with audio data
        """
        try:
            # Clamp duration
            duration_seconds = min(22.0, max(0.5, duration_seconds))

            try:
                response = await self.client.post(
                    f"{self.BASE_URL}/sound-generation", json={"text": prompt, "duration_seconds": duration_seconds}
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"Sound effect API error: {e.response.status_code}")
                return SynthesisResult(success=False, error=f"API request failed with status {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"Connection error: {type(e).__name__}")
                return SynthesisResult(success=False, error="Failed to connect to API")

            if response.status_code == 200:
                audio_data = response.content
                local_path = await self._save_audio(audio_data, "mp3", prefix="sfx_")

                return SynthesisResult(
                    success=True,
                    audio_data=audio_data,
                    local_path=local_path,
                    duration_seconds=duration_seconds,
                    metadata={"type": "sound_effect", "prompt": prompt},
                )
            else:
                error_msg = f"Sound effect generation failed: {response.status_code}"
                logger.error(error_msg)
                return SynthesisResult(success=False, error=error_msg)

        except Exception as e:
            # Log safe error without exposing sensitive information
            logger.error(f"Sound effect error: {type(e).__name__}")
            return SynthesisResult(success=False, error=f"Sound generation failed: {type(e).__name__}")

    async def get_voices(self) -> List[Dict[str, Any]]:
        """
        Get available voices

        Returns:
            List of voice dictionaries
        """
        try:
            response = await self.client.get(f"{self.BASE_URL}/voices")
            if response.status_code == 200:
                data = response.json()
                return data.get("voices", [])  # type: ignore[no-any-return]
            else:
                logger.error(f"Failed to get voices: {response.status_code}")
                return []
        except httpx.RequestError as e:
            logger.error(f"Error getting voices: {type(e).__name__}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting voices: {type(e).__name__}")
            return []

    async def get_voice_by_id(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific voice details

        Args:
            voice_id: Voice ID

        Returns:
            Voice dictionary or None
        """
        try:
            response = await self.client.get(f"{self.BASE_URL}/voices/{voice_id}")
            if response.status_code == 200:
                return response.json()  # type: ignore[no-any-return]
            else:
                logger.error(f"Voice not found: {voice_id}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error getting voice details: {type(e).__name__}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting voice: {type(e).__name__}")
            return None

    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get user subscription info

        Returns:
            User info dictionary or None
        """
        try:
            response = await self.client.get(f"{self.BASE_URL}/user")
            if response.status_code == 200:
                return response.json()  # type: ignore[no-any-return]
            else:
                logger.error(f"Failed to get user info: {response.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error getting user info: {type(e).__name__}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting user info: {type(e).__name__}")
            return None

    async def get_models(self) -> List[Dict[str, Any]]:
        """
        Get available models

        Returns:
            List of model dictionaries
        """
        try:
            response = await self.client.get(f"{self.BASE_URL}/models")
            if response.status_code == 200:
                return response.json()  # type: ignore[no-any-return]
            else:
                logger.error(f"Failed to get models: {response.status_code}")
                return []
        except httpx.RequestError as e:
            logger.error(f"Error getting models: {type(e).__name__}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting models: {type(e).__name__}")
            return []

    async def _save_audio(
        self,
        audio_data: bytes,
        format_str: str,
        prefix: str = "speech_",
        save_to_outputs: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save audio data to local file and outputs directory

        Args:
            audio_data: Audio bytes
            format_str: Format string (mp3, pcm, etc.)
            prefix: File prefix
            save_to_outputs: Also save to outputs directory
            metadata: Additional metadata to save

        Returns:
            Path to saved file
        """
        # Determine file extension
        if "mp3" in format_str.lower():
            ext = "mp3"
        elif "pcm" in format_str.lower():
            ext = "pcm"
        elif "ulaw" in format_str.lower():
            ext = "ulaw"
        else:
            ext = "audio"

        # Generate unique filename
        import time
        from datetime import datetime

        timestamp = int(time.time() * 1000)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}{date_str}_{timestamp}.{ext}"

        # Save to tmp directory
        tmp_dir = Path("/tmp/elevenlabs_audio")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_filepath = tmp_dir / filename

        with open(tmp_filepath, "wb") as f:
            f.write(audio_data)

        logger.info(f"Saved audio to tmp: {tmp_filepath}")

        # Also save to outputs directory if requested
        if save_to_outputs:
            # Use the configured output directory
            outputs_dir = self.output_dir
            outputs_dir.mkdir(parents=True, exist_ok=True)

            # Organize by date
            date_dir = outputs_dir / datetime.now().strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            output_filepath = date_dir / filename
            with open(output_filepath, "wb") as f:
                f.write(audio_data)

            logger.info(f"Saved audio to outputs: {output_filepath}")

            # Save comprehensive metadata
            metadata_file = output_filepath.with_suffix(".json")
            meta = {
                "filename": filename,
                "format": format_str,
                "timestamp": datetime.now().isoformat(),
                "size_bytes": len(audio_data),
                "prefix": prefix,
                "file_path": str(output_filepath),
                "tmp_path": str(tmp_filepath),
            }

            # Merge additional metadata if provided
            if metadata:
                meta.update(metadata)

            with open(metadata_file, "w") as f:
                json.dump(meta, f, indent=2)

        return str(tmp_filepath)

    def _chunk_text(self, text: str, schedule: List[int]) -> List[str]:
        """
        Chunk text according to schedule

        Args:
            text: Text to chunk
            schedule: List of character counts

        Returns:
            List of text chunks
        """
        chunks = []
        position = 0

        for i, chunk_size in enumerate(schedule):
            if position >= len(text):
                break

            # Use remaining schedule for last chunk
            if i == len(schedule) - 1:
                chunks.append(text[position:])
            else:
                chunks.append(text[position : position + chunk_size])
                position += chunk_size

        return chunks


# Convenience functions
async def quick_synthesize(
    text: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb", api_key: Optional[str] = None  # Default voice
) -> Optional[str]:
    """
    Quick synthesis helper

    Args:
        text: Text to synthesize
        voice_id: Voice ID
        api_key: API key

    Returns:
        Path to audio file or None
    """
    async with ElevenLabsClient(api_key) as client:
        config = SynthesisConfig(text=text, voice_id=voice_id, model=VoiceModel.ELEVEN_V3)
        result = await client.synthesize_speech(config)

        if result.success:
            return result.local_path  # type: ignore[no-any-return]
        else:
            logger.error(f"Quick synthesis failed: {result.error}")
            return None
