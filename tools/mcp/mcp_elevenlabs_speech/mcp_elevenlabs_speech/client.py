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

    # Regional endpoints for optimized latency
    REGIONAL_WS_URLS = {
        "us": "wss://api.elevenlabs.io/v1/text-to-speech",
        "eu": "wss://api.eu.residency.elevenlabs.io/v1/text-to-speech",
        "india": "wss://api.in.residency.elevenlabs.io/v1/text-to-speech",
        "global": "wss://api-global-preview.elevenlabs.io/v1/text-to-speech",  # 80-100ms EU/Japan
    }

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
                logger.error("ElevenLabs API error: %s - Voice: %s", e.response.status_code, config.voice_id)
                return SynthesisResult(
                    success=False,
                    error=f"API request failed with status {e.response.status_code}",
                    character_count=len(config.text),
                )
            except httpx.RequestError as e:
                # Log connection error without exposing sensitive data
                logger.error("Connection error to ElevenLabs API: %s", type(e).__name__)
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

            error_msg = f"API error {response.status_code}: {response.text}"
            logger.error(error_msg)
            return SynthesisResult(success=False, error=error_msg, character_count=len(config.text))

        except Exception as e:
            # Log safe error without exposing sensitive information
            logger.error("Synthesis error: %s", type(e).__name__)
            return SynthesisResult(
                success=False, error=f"Synthesis failed: {type(e).__name__}", character_count=len(config.text)
            )

    async def synthesize_with_websocket(self, config: StreamConfig) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesis using WebSocket with optimized latency

        Args:
            config: Stream configuration

        Yields:
            Audio data chunks

        Note:
            WebSockets are NOT available for eleven_v3 model.
            Use Flash v2.5 for lowest latency (~75ms inference).
        """
        import base64

        # Get regional WebSocket URL
        region_key = getattr(config, "region", None)
        if region_key and hasattr(region_key, "value"):
            # Extract region name from enum value URL
            region_str = "us"
            if "eu.residency" in region_key.value:
                region_str = "eu"
            elif "in.residency" in region_key.value:
                region_str = "india"
            elif "global-preview" in region_key.value:
                region_str = "global"
            ws_base = self.REGIONAL_WS_URLS.get(region_str, self.WS_URL)
        else:
            ws_base = self.WS_URL

        # Build WebSocket URL with query parameters
        ws_params = []
        ws_params.append(f"model_id={config.model.value}")
        ws_params.append(f"output_format={config.output_format.value}")

        # Enable auto_mode for automatic generation triggers (reduces latency)
        if getattr(config, "auto_mode", True):
            ws_params.append("auto_mode=true")

        # Set inactivity timeout
        inactivity_timeout = getattr(config, "inactivity_timeout", 20)
        ws_params.append(f"inactivity_timeout={inactivity_timeout}")

        ws_url = f"{ws_base}/{config.voice_id}/stream-input?{'&'.join(ws_params)}"

        logger.info("Connecting to WebSocket: %s (region: %s)", ws_url[:80] + "...", region_key)

        async with websockets.connect(ws_url, extra_headers={"xi-api-key": self.api_key}) as websocket:
            # Send initial configuration
            init_message: Dict[str, Any] = {
                "text": " ",  # Initial empty text to establish connection
                "voice_settings": config.voice_settings.to_dict(),
            }

            # Only include chunk_schedule if auto_mode is disabled
            if not getattr(config, "auto_mode", True):
                init_message["chunk_length_schedule"] = config.chunk_schedule

            await websocket.send(json.dumps(init_message))

            # With auto_mode, send text more naturally (word by word or sentence by sentence)
            if getattr(config, "auto_mode", True):
                # Send full text and let auto_mode handle chunking
                await websocket.send(json.dumps({"text": config.text + " ", "flush": True}))

                # Receive all audio chunks
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        if isinstance(data, bytes):
                            yield data
                        else:
                            response = json.loads(data)
                            if response.get("audio"):
                                # Audio is base64 encoded in JSON response
                                audio_bytes = base64.b64decode(response["audio"])
                                yield audio_bytes
                            if response.get("isFinal"):
                                break
                    except asyncio.TimeoutError:
                        break
            else:
                # Manual chunking mode (legacy behavior)
                text_chunks = self._chunk_text(config.text, config.chunk_schedule)

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
                                response = json.loads(data)
                                if response.get("audio"):
                                    audio_bytes = base64.b64decode(response["audio"])
                                    yield audio_bytes
                                if response.get("isFinal") or response.get("done"):
                                    break
                        except asyncio.TimeoutError:
                            if is_last:
                                break
                            continue

            # Send close message
            await websocket.send(json.dumps({"text": ""}))

    async def stream_speech_http(self, config: SynthesisConfig) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesis using HTTP chunked transfer encoding.

        This is faster than WebSocket when the full text is available upfront
        because there's no buffering overhead.

        Args:
            config: Synthesis configuration

        Yields:
            Audio data chunks as they're generated

        Note:
            Use this method when you have the complete text upfront.
            For real-time text input (e.g., from LLM), use synthesize_with_websocket.
        """
        api_params = config.to_api_params()

        # Build streaming URL
        url = f"{self.BASE_URL}/text-to-speech/{config.voice_id}/stream"
        url += f"?output_format={config.output_format.value}"

        payload = {
            "text": api_params["text"],
            "model_id": api_params["model_id"],
            "voice_settings": api_params["voice_settings"],
        }

        if config.language_code:
            payload["language_code"] = config.language_code

        logger.info("Starting HTTP stream for %d chars", len(config.text))

        try:
            async with self.client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk
        except httpx.HTTPStatusError as e:
            logger.error("HTTP streaming error: %s", e.response.status_code)
            raise
        except httpx.RequestError as e:
            logger.error("HTTP streaming connection error: %s", type(e).__name__)
            raise

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
                logger.error("Sound effect API error: %s", e.response.status_code)
                return SynthesisResult(success=False, error=f"API request failed with status {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error("Connection error: %s", type(e).__name__)
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

            error_msg = f"Sound effect generation failed: {response.status_code}"
            logger.error(error_msg)
            return SynthesisResult(success=False, error=error_msg)

        except Exception as e:
            # Log safe error without exposing sensitive information
            logger.error("Sound effect error: %s", type(e).__name__)
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
                return data.get("voices", [])

            logger.error("Failed to get voices: %s", response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("Error getting voices: %s", type(e).__name__)
            return []
        except Exception as e:
            logger.error("Unexpected error getting voices: %s", type(e).__name__)
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
                return response.json()

            logger.error("Voice not found: %s", voice_id)
            return None
        except httpx.RequestError as e:
            logger.error("Error getting voice details: %s", type(e).__name__)
            return None
        except Exception as e:
            logger.error("Unexpected error getting voice: %s", type(e).__name__)
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
                return response.json()

            logger.error("Failed to get user info: %s", response.status_code)
            return None
        except httpx.RequestError as e:
            logger.error("Error getting user info: %s", type(e).__name__)
            return None
        except Exception as e:
            logger.error("Unexpected error getting user info: %s", type(e).__name__)
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
                return response.json()

            logger.error("Failed to get models: %s", response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("Error getting models: %s", type(e).__name__)
            return []
        except Exception as e:
            logger.error("Unexpected error getting models: %s", type(e).__name__)
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
        from datetime import datetime
        import time

        timestamp = int(time.time() * 1000)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}{date_str}_{timestamp}.{ext}"

        # Save to tmp directory
        tmp_dir = Path("/tmp/elevenlabs_audio")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_filepath = tmp_dir / filename

        with open(tmp_filepath, "wb") as f:
            f.write(audio_data)

        logger.info("Saved audio to tmp: %s", tmp_filepath)

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

            logger.info("Saved audio to outputs: %s", output_filepath)

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

            with open(metadata_file, "w", encoding="utf-8") as f:
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
    text: str,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    api_key: Optional[str] = None,  # Default voice
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
            return result.local_path

        logger.error("Quick synthesis failed: %s", result.error)
        return None
