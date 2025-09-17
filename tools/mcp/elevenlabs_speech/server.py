"""ElevenLabs Speech MCP Server"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from core.base_server import BaseMCPServer  # noqa: E402
from core.utils import setup_logging  # noqa: E402

from .client import ElevenLabsClient  # noqa: E402
from .models import (  # noqa: E402
    AUDIO_TAGS,
    VOICE_PRESETS,
    AudioTagCategory,
    GitHubAudioConfig,
    OutputFormat,
    SynthesisConfig,
    VoiceModel,
    VoiceSettings,
    create_expressive_text,
    parse_audio_tags,
    suggest_tags,
    validate_tag_compatibility,
)
from .text_formatter import AudioTagFormatter  # noqa: E402
from .upload import upload_audio  # noqa: E402
from .utils.model_aware_prompting import ModelAwarePrompter  # noqa: E402
from .utils.prompting import EmotionalEnhancer, NaturalSpeechEnhancer, PromptOptimizer, VoiceDirector  # noqa: E402
from .voice_mapping import (  # noqa: E402
    get_optimal_settings,
    get_voice_id,
    validate_voice_for_model,
)
from .voice_registry import VOICE_IDS  # noqa: E402


class ElevenLabsSpeechMCPServer(BaseMCPServer):
    """MCP Server for ElevenLabs v3 advanced speech synthesis"""

    def __init__(self, project_root: Optional[str] = None):
        super().__init__(
            name="ElevenLabs Speech MCP Server",
            version="1.0.0",
            port=8018,
        )

        self.logger = setup_logging("ElevenLabsSpeechMCP")
        self.project_root = Path(project_root) if project_root else Path.cwd()

        # Load configuration
        self.config = self._load_config()

        # Get output directory from environment or use default
        self.output_dir = Path(os.getenv("MCP_OUTPUT_DIR", self.project_root / "outputs" / "elevenlabs_speech"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ElevenLabs client
        self.client = None
        self._voice_id_cache: Dict[str, str] = {}  # Cache for voice name to ID mapping
        self._voice_cache_initialized = False
        if self.config.get("api_key"):
            self.client = ElevenLabsClient(self.config["api_key"], project_root=self.project_root, output_dir=self.output_dir)
        else:
            self.logger.warning("No ElevenLabs API key configured")

        # Cache directory
        self.cache_dir = Path(self.config.get("cache_dir", "/tmp/elevenlabs_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Track synthesis jobs
        self.synthesis_jobs: Dict[str, Any] = {}

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment or config file"""
        # Try to load .env file if it exists
        env_file = self.project_root / ".env"
        if env_file.exists():
            try:
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value.strip('"').strip("'")
            except Exception as e:
                self.logger.warning(f"Could not load .env file: {e}")

        config = {
            "api_key": os.getenv("ELEVENLABS_API_KEY", ""),
            "default_model": os.getenv("ELEVENLABS_DEFAULT_MODEL", "eleven_v3"),
            "default_voice": os.getenv("ELEVENLABS_DEFAULT_VOICE", "Rachel"),
            "cache_dir": os.getenv("ELEVENLABS_CACHE_DIR", "/tmp/elevenlabs_cache"),
            "max_cache_size_gb": float(os.getenv("ELEVENLABS_MAX_CACHE_SIZE_GB", "10")),
            # Voice settings defaults
            "default_stability": float(os.getenv("ELEVENLABS_DEFAULT_STABILITY", "0.5")),
            "default_similarity": float(os.getenv("ELEVENLABS_DEFAULT_SIMILARITY", "0.75")),
            "default_style": float(os.getenv("ELEVENLABS_DEFAULT_STYLE", "0")),
            "speaker_boost": os.getenv("ELEVENLABS_SPEAKER_BOOST", "false").lower() == "true",
            # Streaming configuration
            "websocket_enabled": os.getenv("ELEVENLABS_WEBSOCKET_ENABLED", "true").lower() == "true",
            "chunk_schedule": json.loads(os.getenv("ELEVENLABS_CHUNK_SCHEDULE", "[120,160,250,290]")),
            "stream_timeout_ms": int(os.getenv("ELEVENLABS_STREAM_TIMEOUT_MS", "20000")),
            # Upload configuration
            "auto_upload": os.getenv("AUDIO_UPLOAD_SERVICE", "auto"),
            "upload_max_size_mb": float(os.getenv("AUDIO_UPLOAD_MAX_SIZE_MB", "50")),
            "upload_format": os.getenv("AUDIO_UPLOAD_FORMAT", "mp3_44100_128"),
        }

        return config

    async def synthesize_speech_v3(
        self,
        text: str,
        voice_id: Optional[str] = None,
        voice_settings: Optional[Dict] = None,
        model: Optional[str] = None,
        output_format: Optional[str] = None,
        language_code: Optional[str] = None,
        upload: bool = True,
        stream: bool = False,
        optimize_prompt: bool = False,
    ) -> Dict[str, Any]:
        """
        Synthesize speech with ElevenLabs

        Supports audio tags like [laughs], [whisper], [excited], etc. (v3 only)
        """
        if not self.client:
            return {"error": "ElevenLabs client not configured"}

        # Initialize voice cache if not done yet
        if not self._voice_cache_initialized:
            await self._initialize_voice_cache()
            self._voice_cache_initialized = True

        # Resolve voice ID using the robust mapping system
        resolved_voice_id = await self._resolve_voice_id(voice_id)
        if not resolved_voice_id:
            return {
                "success": False,
                "error": f"Could not resolve voice: {voice_id}",
                "available_voices": list(self._voice_id_cache.keys()),
            }

        model_enum = VoiceModel(model or self.config["default_model"])

        # Validate voice compatibility with model
        voice_name_for_validation = self._get_voice_name_from_id(resolved_voice_id)
        if voice_name_for_validation:
            is_valid, validation_msg = validate_voice_for_model(voice_name_for_validation, model_enum.value)
        else:
            # Skip validation if we can't find the voice name
            is_valid = True
            validation_msg = "OK"
        if not is_valid:
            self.logger.warning(f"Voice validation failed: {validation_msg}")
            # Try to find a compatible alternative
            resolved_voice_id = await self._find_compatible_voice(model_enum)
            if not resolved_voice_id:
                return {
                    "success": False,
                    "error": validation_msg,
                    "suggestion": "Try using 'rachel' or 'sarah' with eleven_v3",
                }

        # Store original text for metadata
        original_text = text

        # Validate and format audio tags
        is_valid, tag_errors = AudioTagFormatter.validate_tag_syntax(text)
        if not is_valid:
            self.logger.warning(f"Audio tag syntax issues: {tag_errors}")
            # Continue anyway but log the issues

        # Format text with proper audio tag placement
        formatter = AudioTagFormatter()
        text = formatter.format_with_tags(text, auto_segment=True)

        # Clean text based on model capabilities
        text = ModelAwarePrompter.clean_text_for_model(text, model_enum)

        # Optimize prompt if requested
        if optimize_prompt:
            text = PromptOptimizer.optimize_prompt(text)
            # Clean again after optimization to remove any added unsupported tags
            text = ModelAwarePrompter.clean_text_for_model(text, model_enum)

        # Parse voice settings or use optimal settings for the voice
        if voice_settings:
            settings = VoiceSettings(**voice_settings)
        else:
            # Get optimal settings for this specific voice
            voice_name = self._get_voice_name_from_id(resolved_voice_id)
            optimal = get_optimal_settings(voice_name) if voice_name else {}
            settings = VoiceSettings(
                stability=optimal.get("stability", self.config["default_stability"]),
                similarity_boost=optimal.get("similarity_boost", self.config["default_similarity"]),
                style=optimal.get("style", self.config["default_style"]),
                use_speaker_boost=optimal.get("use_speaker_boost", self.config["speaker_boost"]),
            )

        # Create synthesis config
        config = SynthesisConfig(
            text=text,
            voice_id=resolved_voice_id,
            model=model_enum,
            voice_settings=settings,
            output_format=OutputFormat(output_format or self.config["upload_format"]),
            language_code=language_code,
            stream=stream,
        )

        # Synthesize with error handling
        try:
            result = await self.client.synthesize_speech(config)
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            # Try with fallback voice and model
            fallback_voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel
            fallback_model = VoiceModel.ELEVEN_MULTILINGUAL_V2

            self.logger.info(f"Attempting fallback with Rachel voice and {fallback_model.value}")
            config.voice_id = fallback_voice_id
            config.model = fallback_model

            try:
                result = await self.client.synthesize_speech(config)
            except Exception as fallback_error:
                return {
                    "success": False,
                    "error": f"Synthesis failed: {str(e)}",
                    "fallback_error": f"Fallback also failed: {str(fallback_error)}",
                    "suggestion": "Check API key, network connection, and voice availability",
                }

        if result.success and upload and result.local_path:
            # Upload audio with error handling
            try:
                upload_result = upload_audio(result.local_path, self.config["auto_upload"])
                if upload_result:
                    result.audio_url = upload_result
            except Exception as upload_error:
                self.logger.warning(f"Upload failed but synthesis succeeded: {upload_error}")
                # Continue without upload URL

        # Build result dict with proper audio handling
        result_dict = result.to_dict()

        # IMPORTANT: Handle audio data to prevent context window pollution
        # Priority: Local HTTP URL > External URL > base64 (only if small) > nothing
        if result.success:
            if result.audio_url:
                # Best case: We have a URL, no need for raw data
                self.logger.info(f"Returning audio URL: {result.audio_url}")
                # Clear audio_data since we have URL
                if "audio_data" in result_dict:
                    del result_dict["audio_data"]
            elif result.audio_data:
                # We have audio data but no URL - serve it via local HTTP server
                try:
                    # Import the audio file server module
                    import sys
                    from pathlib import Path

                    sys.path.insert(0, str(Path(__file__).parent.parent / "virtual_character"))
                    from audio_file_server import serve_audio_file

                    # Serve the audio file
                    audio_format = config.output_format.value.lower()  # mp3, wav, etc.
                    local_url = await serve_audio_file(result.audio_data, audio_format)
                    result_dict["audio_url"] = local_url
                    self.logger.info(f"Serving audio via local HTTP: {local_url} ({len(result.audio_data)} bytes)")

                    # Clear audio_data since we now have a URL
                    if "audio_data" in result_dict:
                        del result_dict["audio_data"]
                except Exception as e:
                    self.logger.warning(f"Failed to serve audio via local HTTP: {e}")
                    # Fallback: Only include base64 if small
                    if len(result.audio_data) < 50000:  # Only include if < 50KB
                        import base64

                        result_dict["audio_data"] = base64.b64encode(result.audio_data).decode("utf-8")
                        self.logger.info(f"Fallback: Returning small audio as base64 ({len(result.audio_data)} bytes)")
                    else:
                        # Large audio without URL: Don't include to avoid context pollution
                        if "audio_data" in result_dict:
                            del result_dict["audio_data"]
                        self.logger.warning("Audio too large for base64, local server failed. Returning path only.")
            else:
                # No audio data or URL
                self.logger.warning("No audio data or URL available.")

        # Add original text and formatting info to result
        if result_dict.get("metadata"):
            result_dict["metadata"]["original_input"] = original_text
            result_dict["metadata"]["text_was_formatted"] = True
            result_dict["metadata"]["voice_was_validated"] = True

        return result_dict

    async def synthesize_emotional(
        self, text: str, emotions: List[str], voice_id: Optional[str] = None, intensity: str = "natural"
    ) -> Dict[str, Any]:
        """Generate speech with emotional context"""
        # Map emotions to tags
        emotion_tags = []
        for emotion in emotions:
            if emotion in AUDIO_TAGS[AudioTagCategory.EMOTIONS]:
                emotion_tags.append(AUDIO_TAGS[AudioTagCategory.EMOTIONS][emotion])

        # Adjust voice settings based on intensity
        settings_map = {
            "subtle": {"stability": 0.7, "style": 0.1},
            "natural": {"stability": 0.5, "style": 0.3},
            "exaggerated": {"stability": 0.3, "style": 0.6},
        }
        settings = settings_map.get(intensity, settings_map["natural"])

        # Add emotion tags to text
        tagged_text = " ".join(emotion_tags) + " " + text

        return await self.synthesize_speech_v3(text=tagged_text, voice_id=voice_id, voice_settings=settings)

    async def synthesize_dialogue(
        self, script: List[Dict[str, Any]], global_settings: Optional[Dict] = None, mix_audio: bool = True
    ) -> Dict[str, Any]:
        """Generate multi-character dialogue"""
        if not self.client:
            return {"error": "ElevenLabs client not configured"}

        audio_segments = []

        for line in script:
            # Parse line configuration
            character_voice = line.get("character")
            text = line.get("text", "")
            tags = line.get("tags", [])

            # Add tags to text
            if tags:
                tag_text = " ".join(tags)
                text = f"{tag_text} {text}"

            # Synthesize line
            result = await self.synthesize_speech_v3(
                text=text, voice_id=character_voice, voice_settings=line.get("settings_override", global_settings)
            )

            if result.get("success") and result.get("local_path"):
                audio_segments.append(
                    {"path": result["local_path"], "character": character_voice, "duration": result.get("duration_seconds")}
                )

        return {"success": True, "segments": audio_segments, "total_count": len(audio_segments)}

    async def generate_sound_effect(self, prompt: str, duration_seconds: float = 5.0, upload: bool = True) -> Dict[str, Any]:
        """Generate sound effect from description (max 22 seconds)"""
        if not self.client:
            return {"error": "ElevenLabs client not configured"}

        result = await self.client.generate_sound_effect(prompt, duration_seconds)

        if result.success and upload and result.local_path:
            upload_result = upload_audio(result.local_path)
            if upload_result:
                result.audio_url = upload_result

        # Build result dict with proper audio handling
        result_dict = result.to_dict()

        # Apply same audio data handling as synthesize_speech_v3
        if result.success:
            if result.audio_url:
                # Best case: We have a URL, no need for raw data
                self.logger.info(f"Returning sound effect URL: {result.audio_url}")
                if "audio_data" in result_dict:
                    del result_dict["audio_data"]
            elif result.audio_data and len(result.audio_data) < 50000:  # Only include if < 50KB
                # Small audio: Include base64 for convenience
                import base64

                result_dict["audio_data"] = base64.b64encode(result.audio_data).decode("utf-8")
                self.logger.info(f"Returning small sound effect as base64 ({len(result.audio_data)} bytes)")
            else:
                # Large audio without URL: Don't include to avoid context pollution
                if "audio_data" in result_dict:
                    del result_dict["audio_data"]
                self.logger.warning("Sound effect too large for base64, no URL available. Returning path only.")

        return result_dict

    async def generate_pr_audio_response(
        self,
        review_text: str,
        tone: str = "professional",
        add_intro: bool = False,
        add_outro: bool = False,
        auto_post_comment: bool = False,
        pr_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate audio review for GitHub PR"""
        config = GitHubAudioConfig(
            text=review_text,
            tone=tone,
            add_intro=add_intro,
            add_outro=add_outro,
            pr_number=pr_number,
            auto_post_comment=auto_post_comment,
        )

        # Generate full text with intro/outro
        full_text = config.generate_full_text()

        # Select appropriate voice settings
        voice_preset = "github_review"
        settings = VoiceSettings.from_preset(voice_preset)

        # Synthesize
        result = await self.synthesize_speech_v3(text=full_text, voice_settings=settings.to_dict(), upload=True)

        if result.get("success") and result.get("audio_url"):
            # Format GitHub comment
            comment = self._format_github_audio_comment(
                audio_url=result["audio_url"], duration=result.get("duration_seconds"), tone=tone
            )
            result["github_comment"] = comment

        return result

    async def list_available_voices(self) -> Dict[str, Any]:
        """List all available voices"""
        if not self.client:
            return {"error": "ElevenLabs client not configured"}

        voices = await self.client.get_voices()

        # Format voice information
        formatted_voices = []
        for voice in voices:
            formatted_voices.append(
                {
                    "voice_id": voice.get("voice_id"),
                    "name": voice.get("name"),
                    "category": voice.get("category"),
                    "labels": voice.get("labels", {}),
                    "preview_url": voice.get("preview_url"),
                }
            )

        return {"success": True, "voices": formatted_voices, "count": len(formatted_voices)}

    async def parse_audio_tags(self, text: str) -> Dict[str, Any]:
        """Parse and validate audio tags in text"""
        result = parse_audio_tags(text)

        # Add validation if tags found
        if result["has_tags"]:
            validation = validate_tag_compatibility(result["tags_found"])
            result["validation"] = validation

        # Add suggestions
        suggestions = suggest_tags(text, context="general")
        result["suggested_tags"] = suggestions

        return result

    async def suggest_audio_tags(self, text: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Suggest appropriate audio tags for text"""
        suggestions = suggest_tags(text, context)

        # Create example with tags
        if suggestions:
            example = create_expressive_text(text=text, emotion=None, delivery=None, reactions=[])

            # Add first suggestion
            if suggestions:
                example = f"{suggestions[0]} {text}"
        else:
            example = text

        return {"suggestions": suggestions, "example": example, "context": context}

    async def set_voice_preset(self, preset: str) -> Dict[str, Any]:
        """Set voice settings from preset"""
        if preset not in VOICE_PRESETS:
            return {"error": f"Unknown preset: {preset}", "available_presets": list(VOICE_PRESETS.keys())}

        settings = VoiceSettings.from_preset(preset)

        # Update config
        self.config["default_stability"] = settings.stability
        self.config["default_similarity"] = settings.similarity_boost
        self.config["default_style"] = settings.style
        self.config["speaker_boost"] = settings.use_speaker_boost

        return {"success": True, "preset": preset, "settings": settings.to_dict()}

    async def get_user_subscription(self) -> Dict[str, Any]:
        """Get user subscription information"""
        if not self.client:
            return {"error": "ElevenLabs client not configured"}

        user_info = await self.client.get_user_info()

        if user_info:
            return {
                "success": True,
                "subscription": user_info.get("subscription", {}),
                "character_count": user_info.get("character_count"),
                "character_limit": user_info.get("character_limit"),
            }
        else:
            return {"error": "Failed to get user information"}

    async def clear_audio_cache(self) -> Dict[str, Any]:
        """Clear cached audio files"""
        try:
            import shutil

            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)

            return {"success": True, "message": f"Cleared cache at {self.cache_dir}"}
        except Exception as e:
            return {"error": f"Failed to clear cache: {e}"}

    async def _initialize_voice_cache(self):
        """Initialize voice name to ID cache on startup"""
        try:
            # Start with our local registry
            for name, voice_id in VOICE_IDS.items():
                self._voice_id_cache[name.lower()] = voice_id

            # Optionally fetch additional voices from API
            if self.client:
                try:
                    voices = await self.client.get_voices()
                    for voice in voices:
                        voice_name = voice.get("name", "").lower()
                        voice_id = voice.get("voice_id")
                        # Add voices not in our registry
                        if voice_name and voice_id and voice_name not in self._voice_id_cache:
                            self._voice_id_cache[voice_name] = voice_id
                    self.logger.info(f"Cached {len(self._voice_id_cache)} voice mappings (registry + API)")
                except Exception:
                    # If API fails, we still have the registry
                    self.logger.info(f"Using {len(self._voice_id_cache)} voices from local registry")
        except Exception as e:
            self.logger.warning(f"Could not initialize voice cache: {e}")

    def _get_default_voice_id(self) -> str:
        """Get default voice ID from name or return configured ID"""
        default_voice_name = self.config["default_voice"].lower()

        # Try to find voice ID from cache
        if default_voice_name in self._voice_id_cache:
            return self._voice_id_cache[default_voice_name]  # type: ignore[no-any-return]

        # Try the voice registry
        from .voice_registry import get_voice_profile

        profile = get_voice_profile(self.config["default_voice"])
        if profile:
            return profile.voice_id

        # Ultimate fallback
        return VOICE_IDS.get("Rachel", "21m00Tcm4TlvDq8ikWAM")  # Rachel voice as default

    async def _resolve_voice_id(self, voice_input: Optional[str]) -> Optional[str]:
        """
        Resolve voice ID from various input formats using robust mapping

        Args:
            voice_input: Can be voice name, display name, ID, or None

        Returns:
            Resolved voice ID or None
        """
        if not voice_input:
            return self._get_default_voice_id()

        # First try the new robust mapping system
        resolved_id = get_voice_id(voice_input)
        if resolved_id:
            return resolved_id

        # Then check our cache (includes API voices)
        voice_lower = voice_input.lower().strip()
        if voice_lower in self._voice_id_cache:
            return self._voice_id_cache[voice_lower]  # type: ignore[no-any-return]

        # Check if it's already a valid ID format (UUID-like)
        if len(voice_input) > 10 and " " not in voice_input:
            # Might be a voice ID we don't know about
            self.logger.warning(f"Using unknown voice ID directly: {voice_input}")
            return voice_input

        # Log failure to resolve
        self.logger.error(f"Could not resolve voice: {voice_input}")
        return None

    def _get_voice_name_from_id(self, voice_id: str) -> Optional[str]:
        """Get voice name from ID for validation"""
        from .voice_mapping import VOICE_ID_TO_NAME

        # Check our mapping first
        if voice_id in VOICE_ID_TO_NAME:
            return VOICE_ID_TO_NAME[voice_id]

        # Check cache reverse lookup
        for name, vid in self._voice_id_cache.items():
            if vid == voice_id:
                return name

        return None

    async def _find_compatible_voice(self, model: VoiceModel) -> Optional[str]:
        """Find a compatible voice for the given model"""
        from .voice_mapping import VOICE_MAPPING

        # Find first compatible voice
        for voice_name, caps in VOICE_MAPPING.items():
            if model.value in caps.recommended_models:
                if model == VoiceModel.ELEVEN_V3 and not caps.supports_v3:
                    continue
                return caps.voice_id

        # Fallback to Rachel
        return "21m00Tcm4TlvDq8ikWAM"

    def _format_github_audio_comment(
        self, audio_url: str, duration: Optional[float] = None, tone: str = "professional"
    ) -> str:
        """Format audio link for GitHub comment"""
        duration_str = f" ({duration:.1f}s)" if duration else ""

        emoji_map = {"professional": "🎤", "friendly": "🎵", "constructive": "💭", "enthusiastic": "🎉"}
        emoji = emoji_map.get(tone, "🔊")

        return f"{emoji} [Audio Review{duration_str}]({audio_url})"

    async def select_optimal_voice(
        self,
        text: str,
        content_type: Optional[str] = None,
        prefer_gender: Optional[str] = None,
        require_v3: bool = True,
    ) -> Dict[str, Any]:
        """
        Intelligently select the best voice for given content

        Args:
            text: Text to analyze for voice selection
            content_type: Type of content (github_review, documentation, etc.)
            prefer_gender: Preferred gender (male/female/neutral)
            require_v3: Only return v3-compatible voices

        Returns:
            Voice recommendation with details
        """
        from .voice_mapping import VOICE_MAPPING
        from .voice_mapping import ContentType as CT
        from .voice_mapping import get_voice_for_content

        # Auto-detect content type if not provided
        if not content_type:
            text_lower = text.lower()
            if "error" in text_lower or "failed" in text_lower:
                content_type = "error_message"
            elif "success" in text_lower or "completed" in text_lower:
                content_type = "success_message"
            elif "warning" in text_lower or "caution" in text_lower:
                content_type = "warning_message"
            elif any(tag in text for tag in ["[laughs]", "[excited]", "[happy]"]):
                content_type = "casual_chat"
            elif "```" in text or "function" in text or "class" in text:
                content_type = "technical_explanation"
            else:
                content_type = "documentation"  # Default

        # Convert string to enum
        try:
            content_enum = CT(content_type)
        except ValueError:
            content_enum = CT.DOCUMENTATION

        # Get best voice
        voice_name = get_voice_for_content(content_enum, prefer_gender, require_v3)
        voice_caps = VOICE_MAPPING.get(voice_name)

        if not voice_caps:
            return {
                "success": False,
                "error": "Could not find suitable voice",
            }

        return {
            "success": True,
            "selected_voice": {
                "name": voice_name,
                "voice_id": voice_caps.voice_id,
                "display_name": voice_caps.display_name,
                "description": f"{voice_caps.gender} voice, {voice_caps.age_group}, {voice_caps.accents}",
                "quality_rating": voice_caps.overall_quality.value,
                "supports_v3": voice_caps.supports_v3,
                "supports_audio_tags": voice_caps.supports_audio_tags,
                "optimal_settings": get_optimal_settings(voice_name),
            },
            "reasoning": {
                "content_type": content_type,
                "best_for": list(voice_caps.best_for),
                "notes": voice_caps.notes,
            },
            "alternatives": [
                {
                    "name": alt_name,
                    "voice_id": alt_caps.voice_id,
                    "display_name": alt_caps.display_name,
                }
                for alt_name, alt_caps in VOICE_MAPPING.items()
                if alt_name != voice_name and content_enum in alt_caps.best_for and (not require_v3 or alt_caps.supports_v3)
            ][
                :3
            ],  # Top 3 alternatives
        }

    async def synthesize_natural_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        add_imperfections: bool = True,
        add_breathing: bool = True,
        character_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synthesize natural-sounding speech with imperfections"""
        # Enhance for natural speech
        if add_imperfections:
            text = NaturalSpeechEnhancer.add_speech_imperfections(text, add_hesitations=True, add_breathing=add_breathing)

        # Apply character voice if specified
        if character_type:
            text = VoiceDirector.create_character_voice(text, character_type)

        # Optimize prompt
        text = PromptOptimizer.optimize_prompt(text)

        return await self.synthesize_speech_v3(text=text, voice_id=voice_id, optimize_prompt=False)  # Already optimized

    async def synthesize_emotional_progression(
        self, text: str, start_emotion: str, end_emotion: str, voice_id: Optional[str] = None, transition_point: float = 0.5
    ) -> Dict[str, Any]:
        """Synthesize speech with emotional progression"""
        # Add emotional progression
        text = EmotionalEnhancer.add_emotional_progression(
            text, start_emotion=start_emotion, end_emotion=end_emotion, transition_point=transition_point
        )

        return await self.synthesize_speech_v3(text=text, voice_id=voice_id, optimize_prompt=True)

    async def optimize_text_for_synthesis(self, text: str, optimization_level: str = "full") -> Dict[str, Any]:
        """Optimize text for better synthesis quality"""
        original_length = len(text)

        if optimization_level == "minimal":
            optimized = PromptOptimizer.optimize_prompt(text, add_pauses=False, enhance_emphasis=True)
        elif optimization_level == "moderate":
            optimized = PromptOptimizer.optimize_prompt(text, add_pauses=True, enhance_emphasis=True)
        else:  # full
            # Apply all optimizations
            optimized = PromptOptimizer.optimize_prompt(text)
            optimized = NaturalSpeechEnhancer.add_conversational_markers(optimized)

        return {
            "success": True,
            "original_text": text,
            "optimized_text": optimized,
            "original_length": original_length,
            "optimized_length": len(optimized),
            "optimization_level": optimization_level,
            "changes": {
                "length_increase": len(optimized) - original_length,
                "has_pauses": "..." in optimized,
                "has_emphasis": any(word.isupper() for word in optimized.split()),
                "has_tags": "[" in optimized,
            },
        }

    async def get_v3_guidance(self, context: str = "review") -> Dict[str, Any]:
        """Get v3 prompting guidance and examples for agents.

        This helps agents learn to write better v3 prompts WITHOUT modifying their text.
        """
        from .v3_agent_guide import V3AgentGuide

        # Get example for context
        example = V3AgentGuide.get_example_for_context(context)

        # Get best practices
        best_practices = V3AgentGuide.BEST_PRACTICES

        # Get suggested tags
        sentiment_map = {
            "review": "thoughtful",
            "critical": "critical",
            "positive": "positive",
            "casual": "casual",
        }
        suggested_tags = V3AgentGuide.suggest_tags_for_sentiment(sentiment_map.get(context, "thoughtful"))

        return {
            "success": True,
            "context": context,
            "example": example,
            "suggested_tags": suggested_tags,
            "best_practices": best_practices,
            "tips": {
                "minimum_length": "Always use at least 250 characters for v3 stability",
                "line_breaks": "Separate emotional sections with line breaks",
                "punctuation": "Use '...' for pauses and CAPS for emphasis",
                "voice_matching": "Choose tags that match your voice personality",
            },
        }

    async def check_v3_prompt(self, text: str) -> Dict[str, Any]:
        """Check if a prompt is optimized for v3 (without modifying it).

        Helps agents understand if their prompt will work well with v3.
        """
        from .v3_agent_guide import V3AgentGuide

        # Validate length
        validation = V3AgentGuide.validate_prompt_length(text)

        # Analyze quality
        analysis = V3AgentGuide.analyze_prompt_quality(text)

        return {
            "success": True,
            "valid": validation["valid"],
            "length": validation["length"],
            "quality_analysis": analysis,
            "message": validation.get("message", ""),
            "suggestions": analysis.get("suggestions", []),
        }

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get list of available tools with metadata"""
        return {
            "synthesize_speech_v3": {
                "description": "Synthesize speech with ElevenLabs v3 - supports audio tags like [laughs], [whisper], etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to synthesize (can include audio tags)"},
                        "voice_id": {"type": "string", "description": "Voice ID or name"},
                        "voice_settings": {"type": "object", "description": "Voice settings (stability, similarity, etc.)"},
                        "model": {"type": "string", "description": "Model to use (eleven_v3, etc.)"},
                        "output_format": {"type": "string", "description": "Audio format"},
                        "language_code": {"type": "string", "description": "Language code (auto-detect if not provided)"},
                        "upload": {"type": "boolean", "default": True, "description": "Upload to hosting service"},
                        "stream": {"type": "boolean", "default": False, "description": "Use streaming"},
                    },
                    "required": ["text"],
                },
            },
            "synthesize_emotional": {
                "description": "Generate speech with emotional context",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to synthesize"},
                        "emotions": {"type": "array", "items": {"type": "string"}, "description": "List of emotions"},
                        "voice_id": {"type": "string", "description": "Voice ID or name"},
                        "intensity": {"type": "string", "enum": ["subtle", "natural", "exaggerated"], "default": "natural"},
                    },
                    "required": ["text", "emotions"],
                },
            },
            "synthesize_dialogue": {
                "description": "Generate multi-character dialogue",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script": {"type": "array", "description": "Dialogue script with character lines"},
                        "global_settings": {"type": "object", "description": "Global voice settings"},
                        "mix_audio": {"type": "boolean", "default": True, "description": "Combine into single file"},
                    },
                    "required": ["script"],
                },
            },
            "generate_sound_effect": {
                "description": "Generate sound effect from description (max 22 seconds)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Description of the sound effect"},
                        "duration_seconds": {"type": "number", "default": 5.0, "description": "Duration (max 22)"},
                        "upload": {"type": "boolean", "default": True, "description": "Upload to hosting"},
                    },
                    "required": ["prompt"],
                },
            },
            "generate_pr_audio_response": {
                "description": "Generate audio review for GitHub PR",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "review_text": {"type": "string", "description": "Review text"},
                        "tone": {
                            "type": "string",
                            "enum": ["professional", "friendly", "constructive", "enthusiastic"],
                            "default": "professional",
                        },
                        "add_intro": {"type": "boolean", "default": False},
                        "add_outro": {"type": "boolean", "default": False},
                        "pr_number": {"type": "integer", "description": "PR number"},
                    },
                    "required": ["review_text"],
                },
            },
            "list_available_voices": {
                "description": "List all available voices",
                "parameters": {"type": "object", "properties": {}},
            },
            "parse_audio_tags": {
                "description": "Parse and validate audio tags in text",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "Text containing audio tags"}},
                    "required": ["text"],
                },
            },
            "suggest_audio_tags": {
                "description": "Suggest appropriate audio tags for text",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze"},
                        "context": {"type": "string", "description": "Context (e.g., github_review)"},
                    },
                    "required": ["text"],
                },
            },
            "set_voice_preset": {
                "description": "Set voice settings from preset",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "preset": {"type": "string", "description": "Preset name (audiobook, github_review, etc.)"}
                    },
                    "required": ["preset"],
                },
            },
            "get_user_subscription": {
                "description": "Get user subscription information",
                "parameters": {"type": "object", "properties": {}},
            },
            "clear_audio_cache": {
                "description": "Clear cached audio files",
                "parameters": {"type": "object", "properties": {}},
            },
            "synthesize_natural_speech": {
                "description": "Synthesize natural-sounding speech with realistic imperfections",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to synthesize"},
                        "voice_id": {"type": "string", "description": "Voice ID or name"},
                        "add_imperfections": {"type": "boolean", "default": True, "description": "Add natural hesitations"},
                        "add_breathing": {"type": "boolean", "default": True, "description": "Add breathing pauses"},
                        "character_type": {"type": "string", "description": "Character type (narrator, hero, villain, etc.)"},
                    },
                    "required": ["text"],
                },
            },
            "synthesize_emotional_progression": {
                "description": "Synthesize speech with emotional progression from start to end",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to synthesize"},
                        "start_emotion": {
                            "type": "string",
                            "description": "Starting emotion (joy, sadness, anger, fear, surprise)",
                        },
                        "end_emotion": {"type": "string", "description": "Ending emotion"},
                        "voice_id": {"type": "string", "description": "Voice ID or name"},
                        "transition_point": {
                            "type": "number",
                            "default": 0.5,
                            "description": "Where to transition (0.0 to 1.0)",
                        },
                    },
                    "required": ["text", "start_emotion", "end_emotion"],
                },
            },
            "optimize_text_for_synthesis": {
                "description": "Optimize text for better ElevenLabs synthesis quality",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to optimize"},
                        "optimization_level": {"type": "string", "enum": ["minimal", "moderate", "full"], "default": "full"},
                    },
                    "required": ["text"],
                },
            },
            "get_v3_guidance": {
                "description": "Get v3 prompting guidance and examples (doesn't modify your text)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "context": {
                            "type": "string",
                            "description": "Context type (review, critical, positive, casual)",
                            "default": "review",
                        },
                    },
                },
            },
            "check_v3_prompt": {
                "description": "Check if your prompt is optimized for v3 (doesn't modify it)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Your prompt to check"},
                    },
                    "required": ["text"],
                },
            },
            "select_optimal_voice": {
                "description": "Intelligently select the best voice for given content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze for voice selection"},
                        "content_type": {
                            "type": "string",
                            "description": "Type of content (github_review, documentation, tutorial, etc.)",
                        },
                        "prefer_gender": {
                            "type": "string",
                            "enum": ["male", "female", "neutral"],
                            "description": "Preferred voice gender",
                        },
                        "require_v3": {
                            "type": "boolean",
                            "default": True,
                            "description": "Only return v3-compatible voices",
                        },
                    },
                    "required": ["text"],
                },
            },
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self.client:
            await self.client.close()


def main():
    """Run the ElevenLabs Speech MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="ElevenLabs Speech Synthesis MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="stdio",
        help="Server mode (http or stdio)",
    )
    parser.add_argument("--project-root", default=None, help="Project root directory")
    args = parser.parse_args()

    server = ElevenLabsSpeechMCPServer(project_root=args.project_root)

    # Check for API key
    if not server.config.get("api_key"):
        if args.mode == "stdio":
            # In stdio mode, still work but warn about missing key
            import sys

            print("⚠️  No ElevenLabs API key configured. Some features will be limited.", file=sys.stderr)
            print("Add to .env: ELEVENLABS_API_KEY=your_api_key", file=sys.stderr)
        else:
            print("\n⚠️  No ElevenLabs API key configured!")
            print("Please add to your .env file:")
            print("ELEVENLABS_API_KEY=your_api_key_here")
            print("\nGet your API key from: https://elevenlabs.io/api")
            return

    if args.mode == "http":
        print(f"🎙️  Starting ElevenLabs Speech MCP Server on port {server.port}")
        print(f"📁 Cache directory: {server.cache_dir}")
        print(f"🎯 Default model: {server.config['default_model']}")
        print(f"🔊 Default voice: {server.config['default_voice']}")

    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
