"""Synthesis configuration models"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .voice_settings import OutputFormat, VoiceModel, VoiceSettings


@dataclass
class SynthesisConfig:
    """Configuration for speech synthesis"""

    text: str
    voice_id: str
    model: VoiceModel = VoiceModel.ELEVEN_V3
    voice_settings: VoiceSettings = field(default_factory=VoiceSettings)
    output_format: OutputFormat = OutputFormat.MP3_44100_128
    language_code: Optional[str] = None  # Auto-detect if not provided
    upload: bool = True  # Auto-upload to hosting service
    stream: bool = False  # Use streaming
    cache: bool = True  # Use cache

    def to_api_params(self) -> Dict[str, Any]:
        """Convert to ElevenLabs API parameters"""
        params = {
            "text": self.text,
            "voice_id": self.voice_id,
            "model_id": self.model.value,
            "voice_settings": self.voice_settings.to_dict(),
        }

        if self.output_format:
            params["output_format"] = self.output_format.value

        if self.language_code:
            params["language_code"] = self.language_code

        return params


@dataclass
class SynthesisResult:
    """Result from speech synthesis"""

    success: bool
    audio_data: Optional[bytes] = None
    audio_url: Optional[str] = None  # URL if uploaded
    local_path: Optional[str] = None  # Local file path
    duration_seconds: Optional[float] = None
    character_count: int = 0
    model_used: Optional[str] = None
    voice_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "success": self.success,
            "audio_url": self.audio_url,
            "local_path": self.local_path,
            "duration_seconds": self.duration_seconds,
            "character_count": self.character_count,
            "model_used": self.model_used,
            "voice_id": self.voice_id,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class DialogueScript:
    """Configuration for multi-character dialogue"""

    lines: List["DialogueLine"]
    global_settings: Optional[VoiceSettings] = None
    mix_audio: bool = True  # Combine into single file
    crossfade_ms: int = 100  # Crossfade between speakers


@dataclass
class DialogueLine:
    """Single line in a dialogue"""

    character_voice_id: str
    text: str
    tags: List[str] = field(default_factory=list)
    overlap_previous: bool = False
    delay_ms: int = 0  # Delay before speaking
    volume: float = 1.0  # Volume adjustment
    settings_override: Optional[VoiceSettings] = None


@dataclass
class SoundEffectConfig:
    """Configuration for sound effect generation"""

    prompt: str  # Description of the sound
    duration_seconds: float = 5.0  # Max 22 seconds
    upload: bool = True

    def validate(self) -> bool:
        """Validate configuration"""
        if self.duration_seconds > 22:
            self.duration_seconds = 22
        if self.duration_seconds < 0.5:
            self.duration_seconds = 0.5
        return True


@dataclass
class AudioScene:
    """Configuration for complex audio scene"""

    elements: List["AudioElement"]
    master_volume: float = 1.0
    normalize: bool = True
    output_format: OutputFormat = OutputFormat.MP3_44100_128


@dataclass
class AudioElement:
    """Single element in an audio scene"""

    type: str  # "speech", "effect", "music", "ambience"
    content: str  # Text for speech, prompt for effects
    timing: "AudioTiming"
    volume: float = 1.0
    voice_id: Optional[str] = None  # For speech elements
    fade_in_ms: int = 0
    fade_out_ms: int = 0


@dataclass
class AudioTiming:
    """Timing configuration for audio elements"""

    start_ms: int = 0
    duration_ms: Optional[int] = None  # None = full duration
    end_ms: Optional[int] = None  # Alternative to duration


@dataclass
class StreamConfig:
    """Configuration for streaming synthesis"""

    text: str
    voice_id: str
    model: VoiceModel = VoiceModel.ELEVEN_TURBO_V2_5  # Optimized for streaming
    voice_settings: VoiceSettings = field(default_factory=VoiceSettings)
    chunk_schedule: List[int] = field(default_factory=lambda: [120, 160, 250, 290])
    auto_flush: bool = True
    keep_alive: bool = True
    output_format: OutputFormat = OutputFormat.MP3_44100_128

    def to_websocket_params(self) -> Dict[str, Any]:
        """Convert to WebSocket parameters"""
        return {
            "text": self.text,
            "voice_id": self.voice_id,
            "model_id": self.model.value,
            "voice_settings": self.voice_settings.to_dict(),
            "chunk_length_schedule": self.chunk_schedule,
            "flush": self.auto_flush,
            "output_format": self.output_format.value,
        }


@dataclass
class GitHubAudioConfig:
    """Configuration for GitHub integration audio"""

    text: str
    tone: str = "professional"  # professional, friendly, constructive, enthusiastic
    voice_persona: str = "reviewer"  # reviewer, maintainer, contributor
    add_intro: bool = False
    add_outro: bool = False
    include_timestamps: bool = True
    auto_post_comment: bool = False
    pr_number: Optional[int] = None
    issue_number: Optional[int] = None

    def generate_full_text(self) -> str:
        """Generate full text with intro/outro"""
        parts = []

        if self.add_intro:
            intro_map = {
                "professional": "Hello, this is my code review.",
                "friendly": "Hey there! Thanks for the PR, here's my feedback.",
                "constructive": "Hi! I've reviewed your changes and have some suggestions.",
                "enthusiastic": "[excited] Great to see this contribution! Here's my review!",
            }
            parts.append(intro_map.get(self.tone, "Hello, here's my review."))

        parts.append(self.text)

        if self.add_outro:
            outro_map = {
                "professional": "Thank you for your contribution.",
                "friendly": "Thanks again! Looking forward to seeing the updates.",
                "constructive": "Let me know if you need any clarification on my feedback.",
                "enthusiastic": "[cheerfully] Keep up the great work!",
            }
            parts.append(outro_map.get(self.tone, "Thank you."))

        return " ".join(parts)
