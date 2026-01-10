"""
Canonical data models for virtual character animation.

These models provide a universal representation that all backend
adapters can translate to their specific formats.

Includes PAD (Pleasure/Arousal/Dominance) emotion model for smooth
emotion blending and interpolation.
"""

from dataclasses import dataclass, field
from enum import Enum
import math
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


# =============================================================================
# PAD (Pleasure/Arousal/Dominance) Emotion Model
# =============================================================================


@dataclass
class EmotionVector:
    """
    PAD (Pleasure, Arousal, Dominance) model for smooth emotion interpolation.

    This 3D vector space enables:
    - Mathematical blending between emotions
    - Smooth interpolation avoiding "glitchy" state snaps
    - Averaging conflicting emotion signals
    - Direct mapping to animation blend shapes

    Based on research: Mehrabian & Russell (1977), Russell & Mehrabian (1974)

    Attributes:
        pleasure: -1 (unhappy/unpleasant) to +1 (happy/pleasant)
        arousal: -1 (calm/sleepy) to +1 (excited/energized)
        dominance: -1 (submissive/controlled) to +1 (dominant/controlling)
    """

    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0

    def __post_init__(self) -> None:
        """Clamp values to valid range."""
        self.pleasure = max(-1.0, min(1.0, self.pleasure))
        self.arousal = max(-1.0, min(1.0, self.arousal))
        self.dominance = max(-1.0, min(1.0, self.dominance))

    def lerp(self, target: "EmotionVector", t: float) -> "EmotionVector":
        """
        Linear interpolation for smooth transitions.

        Args:
            target: Target emotion vector to interpolate towards
            t: Interpolation factor (0.0 = self, 1.0 = target)

        Returns:
            Interpolated EmotionVector
        """
        t = max(0.0, min(1.0, t))
        return EmotionVector(
            pleasure=self.pleasure + (target.pleasure - self.pleasure) * t,
            arousal=self.arousal + (target.arousal - self.arousal) * t,
            dominance=self.dominance + (target.dominance - self.dominance) * t,
        )

    def distance(self, other: "EmotionVector") -> float:
        """Euclidean distance to another emotion vector."""
        return math.sqrt(
            (self.pleasure - other.pleasure) ** 2
            + (self.arousal - other.arousal) ** 2
            + (self.dominance - other.dominance) ** 2
        )

    def scale(self, intensity: float) -> "EmotionVector":
        """
        Scale emotion vector by intensity (moves towards neutral at low intensity).

        Args:
            intensity: Scale factor (0.0 = neutral, 1.0 = full)

        Returns:
            Scaled EmotionVector
        """
        intensity = max(0.0, min(1.0, intensity))
        return EmotionVector(
            pleasure=self.pleasure * intensity,
            arousal=self.arousal * intensity,
            dominance=self.dominance * intensity,
        )

    def magnitude(self) -> float:
        """Calculate the magnitude (intensity) of this emotion vector."""
        return math.sqrt(self.pleasure**2 + self.arousal**2 + self.dominance**2)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        return {
            "pleasure": round(self.pleasure, 4),
            "arousal": round(self.arousal, 4),
            "dominance": round(self.dominance, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "EmotionVector":
        """Create from dictionary."""
        return cls(
            pleasure=data.get("pleasure", 0.0),
            arousal=data.get("arousal", 0.0),
            dominance=data.get("dominance", 0.0),
        )

    @classmethod
    def neutral(cls) -> "EmotionVector":
        """Return a neutral emotion vector."""
        return cls(0.0, 0.0, 0.0)

    def __add__(self, other: "EmotionVector") -> "EmotionVector":
        """Vector addition."""
        return EmotionVector(
            pleasure=self.pleasure + other.pleasure,
            arousal=self.arousal + other.arousal,
            dominance=self.dominance + other.dominance,
        )

    def __mul__(self, scalar: float) -> "EmotionVector":
        """Scalar multiplication."""
        return EmotionVector(
            pleasure=self.pleasure * scalar,
            arousal=self.arousal * scalar,
            dominance=self.dominance * scalar,
        )


# PAD vectors for each EmotionType
# Values based on psychological research on emotional dimensions
EMOTION_TO_PAD: Dict[EmotionType, EmotionVector] = {
    EmotionType.NEUTRAL: EmotionVector(0.0, 0.0, 0.0),
    EmotionType.HAPPY: EmotionVector(+0.8, +0.5, +0.2),
    EmotionType.SAD: EmotionVector(-0.7, -0.3, -0.4),
    EmotionType.ANGRY: EmotionVector(-0.6, +0.8, +0.6),
    EmotionType.SURPRISED: EmotionVector(+0.2, +0.8, -0.1),
    EmotionType.FEARFUL: EmotionVector(-0.7, +0.7, -0.6),
    EmotionType.DISGUSTED: EmotionVector(-0.6, +0.2, +0.3),
    EmotionType.CONTEMPTUOUS: EmotionVector(-0.3, +0.1, +0.7),
    EmotionType.EXCITED: EmotionVector(+0.8, +0.9, +0.3),
    EmotionType.CALM: EmotionVector(+0.3, -0.6, +0.1),
}


def get_pad_vector(emotion: EmotionType, intensity: float = 1.0) -> EmotionVector:
    """
    Get the PAD vector for an emotion, scaled by intensity.

    Args:
        emotion: The EmotionType
        intensity: Scale factor (0-1)

    Returns:
        Scaled EmotionVector
    """
    base_vector = EMOTION_TO_PAD.get(emotion, EmotionVector.neutral())
    return base_vector.scale(intensity)


def find_closest_emotion(vector: EmotionVector) -> EmotionType:
    """
    Find the EmotionType closest to a given PAD vector.

    Useful for converting blended emotions back to discrete types.

    Args:
        vector: The PAD vector to match

    Returns:
        Closest EmotionType
    """
    closest_emotion = EmotionType.NEUTRAL
    min_distance = float("inf")

    for emotion, pad in EMOTION_TO_PAD.items():
        distance = vector.distance(pad)
        if distance < min_distance:
            min_distance = distance
            closest_emotion = emotion

    return closest_emotion


def blend_emotions(
    emotions: List[tuple[EmotionType, float]],
) -> tuple[EmotionType, float]:
    """
    Blend multiple emotions with weights into a single result.

    Args:
        emotions: List of (EmotionType, weight) tuples

    Returns:
        (blended EmotionType, intensity)
    """
    if not emotions:
        return EmotionType.NEUTRAL, 0.0

    # Accumulate weighted PAD vectors
    total_weight = sum(weight for _, weight in emotions)
    if total_weight == 0:
        return EmotionType.NEUTRAL, 0.0

    blended = EmotionVector.neutral()
    for emotion, weight in emotions:
        pad = get_pad_vector(emotion, weight / total_weight)
        blended = blended + pad

    # Find closest discrete emotion
    result_emotion = find_closest_emotion(blended)
    result_intensity = min(blended.magnitude(), 1.0)

    return result_emotion, result_intensity


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
    BACKFLIP = "backflip"
    CHEER = "cheer"
    DIE = "die"
    SADNESS = "sadness"


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        data: Dict[str, Any] = {
            "world_name": self.world_name,
            "instance_id": self.instance_id,
            "nearby_agents": self.nearby_agents,
            "nearby_objects": self.nearby_objects,
            "active_zones": self.active_zones,
        }

        if self.agent_position:
            data["agent_position"] = self.agent_position.to_list()
        if self.agent_rotation:
            data["agent_rotation"] = self.agent_rotation.to_list()
        if self.time_of_day is not None:
            data["time_of_day"] = self.time_of_day
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
        if not prev_frame and next_frame:
            return next_frame
        if prev_frame and next_frame:
            return self._interpolate_frames(prev_frame, next_frame, time)

        return None

    def _interpolate_frames(
        self,
        frame_a: CanonicalAnimationData,
        frame_b: CanonicalAnimationData,
        target_time: float,
    ) -> CanonicalAnimationData:
        """Interpolate between two animation frames."""
        # Calculate interpolation factor (0.0 = frame_a, 1.0 = frame_b)
        time_range = frame_b.timestamp - frame_a.timestamp
        if time_range <= 0:
            return frame_a
        t = (target_time - frame_a.timestamp) / time_range
        t = max(0.0, min(1.0, t))  # Clamp to [0, 1]

        # Create interpolated frame
        result = CanonicalAnimationData(timestamp=target_time)

        # Interpolate blend shapes (linear)
        all_blend_shapes = set(frame_a.blend_shapes.keys()) | set(frame_b.blend_shapes.keys())
        for shape in all_blend_shapes:
            val_a = frame_a.blend_shapes.get(shape, 0.0)
            val_b = frame_b.blend_shapes.get(shape, 0.0)
            result.blend_shapes[shape] = val_a + (val_b - val_a) * t

        # Interpolate visemes (linear)
        all_visemes = set(frame_a.visemes.keys()) | set(frame_b.visemes.keys())
        for viseme in all_visemes:
            val_a = frame_a.visemes.get(viseme, 0.0)
            val_b = frame_b.visemes.get(viseme, 0.0)
            result.visemes[viseme] = val_a + (val_b - val_a) * t

        # Interpolate bone transforms
        all_bones = set(frame_a.bone_transforms.keys()) | set(frame_b.bone_transforms.keys())
        for bone in all_bones:
            if bone in frame_a.bone_transforms and bone in frame_b.bone_transforms:
                transform_a = frame_a.bone_transforms[bone]
                transform_b = frame_b.bone_transforms[bone]
                result.bone_transforms[bone] = self._interpolate_transforms(transform_a, transform_b, t)
            elif bone in frame_a.bone_transforms:
                result.bone_transforms[bone] = frame_a.bone_transforms[bone]
            else:
                result.bone_transforms[bone] = frame_b.bone_transforms[bone]

        # Use emotion/gesture from the frame we're closer to
        if t < 0.5:
            result.emotion = frame_a.emotion
            result.emotion_intensity = frame_a.emotion_intensity
            result.gesture = frame_a.gesture
            result.gesture_intensity = frame_a.gesture_intensity
        else:
            result.emotion = frame_b.emotion
            result.emotion_intensity = frame_b.emotion_intensity
            result.gesture = frame_b.gesture
            result.gesture_intensity = frame_b.gesture_intensity

        # Interpolate numeric parameters, copy non-numeric
        all_params = set(frame_a.parameters.keys()) | set(frame_b.parameters.keys())
        for param in all_params:
            param_a: Any = frame_a.parameters.get(param)
            param_b: Any = frame_b.parameters.get(param)
            if isinstance(param_a, (int, float)) and isinstance(param_b, (int, float)):
                result.parameters[param] = param_a + (param_b - param_a) * t
            elif t < 0.5 and param_a is not None:
                result.parameters[param] = param_a
            elif param_b is not None:
                result.parameters[param] = param_b

        # Locomotion - use closest frame's data
        result.locomotion = frame_a.locomotion if t < 0.5 else frame_b.locomotion

        # Audio timestamp interpolation
        if frame_a.audio_timestamp is not None and frame_b.audio_timestamp is not None:
            result.audio_timestamp = frame_a.audio_timestamp + (frame_b.audio_timestamp - frame_a.audio_timestamp) * t
        elif t < 0.5:
            result.audio_timestamp = frame_a.audio_timestamp
        else:
            result.audio_timestamp = frame_b.audio_timestamp

        return result

    def _interpolate_transforms(self, transform_a: Transform, transform_b: Transform, t: float) -> Transform:
        """Interpolate between two transforms using linear interpolation."""
        # Linear interpolation for position
        pos = Vector3(
            x=transform_a.position.x + (transform_b.position.x - transform_a.position.x) * t,
            y=transform_a.position.y + (transform_b.position.y - transform_a.position.y) * t,
            z=transform_a.position.z + (transform_b.position.z - transform_a.position.z) * t,
        )

        # SLERP for quaternion rotation (simplified linear interpolation for now)
        # Full SLERP would require checking for shortest path and proper spherical interpolation
        rot = self._slerp_quaternion(transform_a.rotation, transform_b.rotation, t)

        # Linear interpolation for scale
        scale = Vector3(
            x=transform_a.scale.x + (transform_b.scale.x - transform_a.scale.x) * t,
            y=transform_a.scale.y + (transform_b.scale.y - transform_a.scale.y) * t,
            z=transform_a.scale.z + (transform_b.scale.z - transform_a.scale.z) * t,
        )

        return Transform(position=pos, rotation=rot, scale=scale)

    def _slerp_quaternion(self, q_a: Quaternion, q_b: Quaternion, t: float) -> Quaternion:
        """Spherical linear interpolation between two quaternions."""
        # Calculate dot product
        dot = q_a.w * q_b.w + q_a.x * q_b.x + q_a.y * q_b.y + q_a.z * q_b.z

        # If dot is negative, negate q_b to take shortest path
        if dot < 0:
            q_b = Quaternion(w=-q_b.w, x=-q_b.x, y=-q_b.y, z=-q_b.z)
            dot = -dot

        # If quaternions are very close, use linear interpolation
        if dot > 0.9995:
            result = Quaternion(
                w=q_a.w + (q_b.w - q_a.w) * t,
                x=q_a.x + (q_b.x - q_a.x) * t,
                y=q_a.y + (q_b.y - q_a.y) * t,
                z=q_a.z + (q_b.z - q_a.z) * t,
            )
            # Normalize
            length = np.sqrt(result.w**2 + result.x**2 + result.y**2 + result.z**2)
            return Quaternion(w=result.w / length, x=result.x / length, y=result.y / length, z=result.z / length)

        # Calculate SLERP
        theta_0 = np.arccos(dot)
        theta = theta_0 * t
        sin_theta = np.sin(theta)
        sin_theta_0 = np.sin(theta_0)

        s0 = np.cos(theta) - dot * sin_theta / sin_theta_0
        s1 = sin_theta / sin_theta_0

        return Quaternion(
            w=s0 * q_a.w + s1 * q_b.w,
            x=s0 * q_a.x + s1 * q_b.x,
            y=s0 * q_a.y + s1 * q_b.y,
            z=s0 * q_a.z + s1 * q_b.z,
        )


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
