"""
Canonical data models for virtual character animation.

These models provide a universal representation that all backend
adapters can translate to their specific formats.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


class EmotionType(Enum):
    """Standard emotion types."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    FEARFUL = "fearful"
    DISGUSTED = "disgusted"
    CONTEMPTUOUS = "contemptuous"
    EXCITED = "excited"
    CALM = "calm"


class GestureType(Enum):
    """Standard gesture types."""

    NONE = "none"
    WAVE = "wave"
    POINT = "point"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CLAP = "clap"
    NOD = "nod"
    SHAKE_HEAD = "shake_head"
    SHRUG = "shrug"
    CROSSED_ARMS = "crossed_arms"
    THINKING = "thinking"
    DANCE = "dance"


class VisemeType(Enum):
    """Standard viseme set for lip-sync."""

    NEUTRAL = "neutral"  # Closed/neutral mouth
    AA = "aa"  # As in "father"
    EE = "ee"  # As in "bee"
    IH = "ih"  # As in "bit"
    OH = "oh"  # As in "go"
    UH = "uh"  # As in "book"
    MM = "mm"  # M/B/P bilabial closure
    FV = "fv"  # F/V labiodental
    TH = "th"  # As in "think"
    L = "l"  # Tongue tip up
    R = "r"  # Retroflex
    SZ = "sz"  # S/Z sibilant
    SH = "sh"  # SH/CH postalveolar
    NG = "ng"  # N/NG nasal


@dataclass
class Vector3:
    """3D vector for position, velocity, etc."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_list(self) -> List[float]:
        """Convert to list format."""
        return [self.x, self.y, self.z]

    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([self.x, self.y, self.z])

    @classmethod
    def from_list(cls, values: List[float]) -> "Vector3":
        """Create from list."""
        return cls(values[0], values[1], values[2])


@dataclass
class Quaternion:
    """Quaternion for rotations."""

    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_list(self) -> List[float]:
        """Convert to list format."""
        return [self.w, self.x, self.y, self.z]

    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([self.w, self.x, self.y, self.z])

    @classmethod
    def from_euler(cls, x: float, y: float, z: float) -> "Quaternion":
        """Create from Euler angles (radians)."""
        # Simplified conversion - would use proper math library in production
        cy = np.cos(z * 0.5)
        sy = np.sin(z * 0.5)
        cp = np.cos(y * 0.5)
        sp = np.sin(y * 0.5)
        cr = np.cos(x * 0.5)
        sr = np.sin(x * 0.5)

        return cls(
            w=cr * cp * cy + sr * sp * sy,
            x=sr * cp * cy - cr * sp * sy,
            y=cr * sp * cy + sr * cp * sy,
            z=cr * cp * sy - sr * sp * cy,
        )


@dataclass
class Transform:
    """Complete 3D transform."""

    position: Vector3 = field(default_factory=Vector3)
    rotation: Quaternion = field(default_factory=Quaternion)
    scale: Vector3 = field(default_factory=lambda: Vector3(1.0, 1.0, 1.0))

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {"position": self.position.to_list(), "rotation": self.rotation.to_list(), "scale": self.scale.to_list()}


@dataclass
class LocomotionState:
    """Character locomotion state."""

    velocity: Vector3 = field(default_factory=Vector3)
    is_grounded: bool = True
    movement_mode: str = "idle"  # idle, walk, run, fly, swim
    direction: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 1.0))
    speed: float = 0.0


@dataclass
class CanonicalAnimationData:
    """Universal animation data format."""

    timestamp: float

    # Skeletal animation
    bone_transforms: Dict[str, Transform] = field(default_factory=dict)

    # Facial animation
    blend_shapes: Dict[str, float] = field(default_factory=dict)
    visemes: Dict[VisemeType, float] = field(default_factory=dict)

    # High-level states
    emotion: Optional[EmotionType] = None
    emotion_intensity: float = 1.0
    gesture: Optional[GestureType] = None
    gesture_intensity: float = 1.0

    # Procedural parameters (backend-specific)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Locomotion
    locomotion: Optional[LocomotionState] = None

    # Audio sync
    audio_timestamp: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = {
            "timestamp": self.timestamp,
            "bone_transforms": {name: transform.to_dict() for name, transform in self.bone_transforms.items()},
            "blend_shapes": self.blend_shapes,
            "visemes": {viseme.value: weight for viseme, weight in self.visemes.items()},
            "parameters": self.parameters,
        }

        if self.emotion:
            data["emotion"] = self.emotion.value
            data["emotion_intensity"] = self.emotion_intensity

        if self.gesture:
            data["gesture"] = self.gesture.value
            data["gesture_intensity"] = self.gesture_intensity

        if self.locomotion:
            data["locomotion"] = {
                "velocity": self.locomotion.velocity.to_list(),
                "is_grounded": self.locomotion.is_grounded,
                "movement_mode": self.locomotion.movement_mode,
                "direction": self.locomotion.direction.to_list(),
                "speed": self.locomotion.speed,
            }

        if self.audio_timestamp is not None:
            data["audio_timestamp"] = self.audio_timestamp

        return data


@dataclass
class AudioData:
    """Audio data with metadata."""

    data: bytes
    sample_rate: int = 44100
    channels: int = 1
    format: str = "pcm"  # pcm, mp3, opus, etc.
    duration: float = 0.0

    # Optional metadata
    text: Optional[str] = None
    language: Optional[str] = None
    voice: Optional[str] = None

    # Lip sync and expression data
    viseme_timestamps: Optional[List[tuple[float, VisemeType, float]]] = None  # (time, viseme, weight)
    expression_tags: Optional[List[str]] = None  # ElevenLabs audio tags like [laughs], [whisper]

    # For streaming
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    is_final_chunk: bool = True


@dataclass
class VideoFrame:
    """Single video frame data."""

    data: bytes
    width: int
    height: int
    format: str = "jpeg"  # jpeg, png, raw
    timestamp: float = 0.0
    frame_number: int = 0


@dataclass
class EnvironmentState:
    """Virtual environment state information."""

    world_name: Optional[str] = None
    instance_id: Optional[str] = None

    # Agent information
    agent_position: Optional[Vector3] = None
    agent_rotation: Optional[Quaternion] = None

    # Nearby entities
    nearby_agents: List[Dict[str, Any]] = field(default_factory=list)
    nearby_objects: List[Dict[str, Any]] = field(default_factory=list)

    # Interaction zones
    active_zones: List[str] = field(default_factory=list)

    # Environmental conditions
    time_of_day: Optional[float] = None  # 0-24 hours
    weather: Optional[str] = None
    ambient_audio: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        data = {
            "world_name": self.world_name,
            "instance_id": self.instance_id,
            "nearby_agents": self.nearby_agents,
            "nearby_objects": self.nearby_objects,
            "active_zones": self.active_zones,
        }

        if self.agent_position:
            data["agent_position"] = self.agent_position.to_list()  # type: ignore
        if self.agent_rotation:
            data["agent_rotation"] = self.agent_rotation.to_list()  # type: ignore
        if self.time_of_day is not None:
            data["time_of_day"] = self.time_of_day  # type: ignore
        if self.weather:
            data["weather"] = self.weather
        if self.ambient_audio:
            data["ambient_audio"] = self.ambient_audio

        return data


@dataclass
class AnimationSequence:
    """A sequence of animation keyframes."""

    name: str
    duration: float
    keyframes: List[CanonicalAnimationData]
    loop: bool = False

    def get_frame_at_time(self, time: float) -> Optional[CanonicalAnimationData]:
        """Get interpolated frame at specific time."""
        if not self.keyframes:
            return None

        # Find surrounding keyframes
        prev_frame = None
        next_frame = None

        for frame in self.keyframes:
            if frame.timestamp <= time:
                prev_frame = frame
            elif frame.timestamp > time and next_frame is None:
                next_frame = frame
                break

        if prev_frame and not next_frame:
            return prev_frame
        elif not prev_frame and next_frame:
            return next_frame
        elif prev_frame and next_frame:
            # TODO: Implement interpolation
            return prev_frame

        return None


class EventType(Enum):
    """Types of events in a sequence."""

    ANIMATION = "animation"  # Animation data
    AUDIO = "audio"  # Audio playback
    WAIT = "wait"  # Pause/delay
    LOOP_START = "loop_start"  # Mark loop beginning
    LOOP_END = "loop_end"  # Mark loop end
    PARALLEL = "parallel"  # Events to run in parallel
    EXPRESSION = "expression"  # Expression change
    MOVEMENT = "movement"  # Movement command


@dataclass
class SequenceEvent:
    """Individual event in an event sequence."""

    event_type: EventType
    timestamp: float  # When to trigger (relative to sequence start)
    duration: Optional[float] = None  # Event duration (if applicable)

    # Event-specific data
    animation_data: Optional[CanonicalAnimationData] = None
    audio_data: Optional[AudioData] = None
    wait_duration: Optional[float] = None
    loop_count: Optional[int] = None
    parallel_events: Optional[List["SequenceEvent"]] = None

    # For high-level events
    expression: Optional[EmotionType] = None
    expression_intensity: Optional[float] = None
    movement_params: Optional[Dict[str, Any]] = None

    # Sync settings
    sync_with_audio: bool = False  # Sync animation timing with audio duration
    fade_in: float = 0.0  # Fade in time
    fade_out: float = 0.0  # Fade out time


@dataclass
class EventSequence:
    """Complete sequence of synchronized events."""

    name: str
    description: Optional[str] = None
    events: List[SequenceEvent] = field(default_factory=list)
    total_duration: Optional[float] = None

    # Playback settings
    loop: bool = False
    interrupt_current: bool = True  # Whether to interrupt current sequence
    priority: int = 0  # Higher priority sequences override lower ones

    # Metadata
    created_timestamp: Optional[float] = None
    tags: List[str] = field(default_factory=list)

    def add_event(self, event: SequenceEvent) -> None:
        """Add an event to the sequence."""
        self.events.append(event)
        # Update total duration if needed
        if event.timestamp + (event.duration or 0) > (self.total_duration or 0):
            self.total_duration = event.timestamp + (event.duration or 0)

    def add_animation(self, timestamp: float, animation: CanonicalAnimationData, sync_with_audio: bool = False) -> None:
        """Add animation event."""
        self.add_event(
            SequenceEvent(
                event_type=EventType.ANIMATION, timestamp=timestamp, animation_data=animation, sync_with_audio=sync_with_audio
            )
        )

    def add_audio(self, timestamp: float, audio: AudioData) -> None:
        """Add audio event."""
        self.add_event(
            SequenceEvent(event_type=EventType.AUDIO, timestamp=timestamp, duration=audio.duration, audio_data=audio)
        )

    def add_wait(self, timestamp: float, duration: float) -> None:
        """Add wait/delay event."""
        self.add_event(SequenceEvent(event_type=EventType.WAIT, timestamp=timestamp, wait_duration=duration))

    def add_parallel_events(self, timestamp: float, events: List[SequenceEvent]) -> None:
        """Add events to run in parallel."""
        self.add_event(SequenceEvent(event_type=EventType.PARALLEL, timestamp=timestamp, parallel_events=events))

    def get_events_at_time(self, time: float, tolerance: float = 0.05) -> List[SequenceEvent]:
        """Get events that should trigger at the given time."""
        triggered_events = []
        for event in self.events:
            if abs(event.timestamp - time) <= tolerance:
                triggered_events.append(event)
        return triggered_events
