"""
Unit tests for canonical data models.
"""

import numpy as np

from tools.mcp.mcp_virtual_character.mcp_virtual_character.models.canonical import (
    AnimationSequence,
    AudioData,
    CanonicalAnimationData,
    EmotionType,
    EnvironmentState,
    GestureType,
    LocomotionState,
    Quaternion,
    Transform,
    Vector3,
    VideoFrame,
    VisemeType,
)


class TestVector3:
    """Test Vector3 class."""

    def test_creation(self):
        """Test Vector3 creation."""
        v = Vector3(1.0, 2.0, 3.0)
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0

    def test_to_list(self):
        """Test conversion to list."""
        v = Vector3(1.0, 2.0, 3.0)
        assert v.to_list() == [1.0, 2.0, 3.0]

    def test_to_numpy(self):
        """Test conversion to numpy array."""
        v = Vector3(1.0, 2.0, 3.0)
        arr = v.to_numpy()
        assert isinstance(arr, np.ndarray)
        assert arr.shape == (3,)
        assert np.array_equal(arr, np.array([1.0, 2.0, 3.0]))

    def test_from_list(self):
        """Test creation from list."""
        v = Vector3.from_list([4.0, 5.0, 6.0])
        assert v.x == 4.0
        assert v.y == 5.0
        assert v.z == 6.0


class TestQuaternion:
    """Test Quaternion class."""

    def test_creation(self):
        """Test Quaternion creation."""
        q = Quaternion(1.0, 0.0, 0.0, 0.0)
        assert q.w == 1.0
        assert q.x == 0.0
        assert q.y == 0.0
        assert q.z == 0.0

    def test_to_list(self):
        """Test conversion to list."""
        q = Quaternion(1.0, 0.5, 0.3, 0.1)
        assert q.to_list() == [1.0, 0.5, 0.3, 0.1]

    def test_from_euler(self):
        """Test creation from Euler angles."""
        q = Quaternion.from_euler(0.0, 0.0, 0.0)
        assert abs(q.w - 1.0) < 0.001
        assert abs(q.x) < 0.001
        assert abs(q.y) < 0.001
        assert abs(q.z) < 0.001


class TestTransform:
    """Test Transform class."""

    def test_creation(self):
        """Test Transform creation."""
        t = Transform()
        assert t.position.x == 0.0
        assert t.rotation.w == 1.0
        assert t.scale.x == 1.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        t = Transform(position=Vector3(1.0, 2.0, 3.0), rotation=Quaternion(1.0, 0.0, 0.0, 0.0), scale=Vector3(2.0, 2.0, 2.0))

        d = t.to_dict()
        assert d["position"] == [1.0, 2.0, 3.0]
        assert d["rotation"] == [1.0, 0.0, 0.0, 0.0]
        assert d["scale"] == [2.0, 2.0, 2.0]


class TestCanonicalAnimationData:
    """Test CanonicalAnimationData class."""

    def test_creation(self):
        """Test CanonicalAnimationData creation."""
        anim = CanonicalAnimationData(timestamp=1.0)
        assert anim.timestamp == 1.0
        assert anim.emotion is None
        assert anim.gesture is None
        assert len(anim.bone_transforms) == 0
        assert len(anim.blend_shapes) == 0

    def test_with_emotion(self):
        """Test animation with emotion."""
        anim = CanonicalAnimationData(timestamp=1.0, emotion=EmotionType.HAPPY, emotion_intensity=0.8)
        assert anim.emotion == EmotionType.HAPPY
        assert anim.emotion_intensity == 0.8

    def test_with_gesture(self):
        """Test animation with gesture."""
        anim = CanonicalAnimationData(timestamp=1.0, gesture=GestureType.WAVE, gesture_intensity=1.0)
        assert anim.gesture == GestureType.WAVE
        assert anim.gesture_intensity == 1.0

    def test_with_visemes(self):
        """Test animation with visemes."""
        anim = CanonicalAnimationData(timestamp=1.0, visemes={VisemeType.AA: 0.5, VisemeType.EE: 0.3})
        assert anim.visemes[VisemeType.AA] == 0.5
        assert anim.visemes[VisemeType.EE] == 0.3

    def test_to_dict(self):
        """Test conversion to dictionary."""
        anim = CanonicalAnimationData(
            timestamp=1.0, emotion=EmotionType.HAPPY, gesture=GestureType.WAVE, blend_shapes={"smile": 0.8}
        )

        d = anim.to_dict()
        assert d["timestamp"] == 1.0
        assert d["emotion"] == "happy"
        assert d["gesture"] == "wave"
        assert d["blend_shapes"]["smile"] == 0.8


class TestAudioData:
    """Test AudioData class."""

    def test_creation(self):
        """Test AudioData creation."""
        audio = AudioData(data=b"test_audio_data", sample_rate=44100, channels=2, format="mp3", duration=5.0)
        assert audio.data == b"test_audio_data"
        assert audio.sample_rate == 44100
        assert audio.channels == 2
        assert audio.format == "mp3"
        assert audio.duration == 5.0

    def test_with_metadata(self):
        """Test AudioData with metadata."""
        audio = AudioData(data=b"test", text="Hello world", language="en", voice="Rachel")
        assert audio.text == "Hello world"
        assert audio.language == "en"
        assert audio.voice == "Rachel"


class TestVideoFrame:
    """Test VideoFrame class."""

    def test_creation(self):
        """Test VideoFrame creation."""
        frame = VideoFrame(data=b"frame_data", width=640, height=480, format="jpeg", timestamp=1.5, frame_number=42)
        assert frame.data == b"frame_data"
        assert frame.width == 640
        assert frame.height == 480
        assert frame.format == "jpeg"
        assert frame.timestamp == 1.5
        assert frame.frame_number == 42


class TestEnvironmentState:
    """Test EnvironmentState class."""

    def test_creation(self):
        """Test EnvironmentState creation."""
        state = EnvironmentState(world_name="TestWorld", instance_id="test_123")
        assert state.world_name == "TestWorld"
        assert state.instance_id == "test_123"
        assert len(state.nearby_agents) == 0
        assert len(state.nearby_objects) == 0

    def test_with_position(self):
        """Test EnvironmentState with agent position."""
        state = EnvironmentState(agent_position=Vector3(1.0, 2.0, 3.0), agent_rotation=Quaternion(1.0, 0.0, 0.0, 0.0))
        assert state.agent_position.x == 1.0
        assert state.agent_rotation.w == 1.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        state = EnvironmentState(
            world_name="TestWorld",
            agent_position=Vector3(1.0, 2.0, 3.0),
            nearby_agents=[{"id": "agent1", "name": "TestAgent"}],
        )

        d = state.to_dict()
        assert d["world_name"] == "TestWorld"
        assert d["agent_position"] == [1.0, 2.0, 3.0]
        assert len(d["nearby_agents"]) == 1
        assert d["nearby_agents"][0]["id"] == "agent1"


class TestLocomotionState:
    """Test LocomotionState class."""

    def test_creation(self):
        """Test LocomotionState creation."""
        loco = LocomotionState(velocity=Vector3(1.0, 0.0, 0.0), is_grounded=True, movement_mode="walk", speed=2.5)
        assert loco.velocity.x == 1.0
        assert loco.is_grounded is True
        assert loco.movement_mode == "walk"
        assert loco.speed == 2.5


class TestAnimationSequence:
    """Test AnimationSequence class."""

    def test_creation(self):
        """Test AnimationSequence creation."""
        keyframes = [
            CanonicalAnimationData(timestamp=0.0),
            CanonicalAnimationData(timestamp=1.0),
            CanonicalAnimationData(timestamp=2.0),
        ]

        seq = AnimationSequence(name="test_sequence", duration=2.0, keyframes=keyframes, loop=True)

        assert seq.name == "test_sequence"
        assert seq.duration == 2.0
        assert len(seq.keyframes) == 3
        assert seq.loop is True

    def test_get_frame_at_time(self):
        """Test getting frame at specific time."""
        keyframes = [
            CanonicalAnimationData(timestamp=0.0),
            CanonicalAnimationData(timestamp=1.0),
            CanonicalAnimationData(timestamp=2.0),
        ]

        seq = AnimationSequence(name="test", duration=2.0, keyframes=keyframes)

        # Test exact match
        frame = seq.get_frame_at_time(1.0)
        assert frame is not None
        assert frame.timestamp == 1.0

        # Test interpolation (returns previous frame for now)
        frame = seq.get_frame_at_time(0.5)
        assert frame is not None
        assert frame.timestamp == 0.0

        # Test beyond last frame
        frame = seq.get_frame_at_time(3.0)
        assert frame is not None
        assert frame.timestamp == 2.0

    def test_empty_sequence(self):
        """Test empty animation sequence."""
        seq = AnimationSequence(name="empty", duration=0.0, keyframes=[])

        frame = seq.get_frame_at_time(0.0)
        assert frame is None
