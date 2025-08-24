"""
Unit tests for backend adapter and mock backend.
"""

import asyncio

import pytest
import pytest_asyncio

from ..backends.base import BackendCapabilities
from ..backends.mock import MockBackend
from ..models.canonical import AudioData, CanonicalAnimationData, EmotionType, GestureType


class TestBackendCapabilities:
    """Test BackendCapabilities class."""

    def test_creation(self):
        """Test BackendCapabilities creation."""
        caps = BackendCapabilities()
        assert caps.audio is False
        assert caps.animation is False
        assert caps.video_capture is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        caps = BackendCapabilities()
        caps.audio = True
        caps.animation = True

        d = caps.to_dict()
        assert d["audio"] is True
        assert d["animation"] is True
        assert d["video_capture"] is False


class TestMockBackend:
    """Test MockBackend implementation."""

    @pytest_asyncio.fixture
    async def backend(self):
        """Create mock backend instance."""
        backend = MockBackend()
        yield backend
        if backend.is_connected:
            await backend.disconnect()

    @pytest.mark.asyncio
    async def test_connect(self, backend):
        """Test connecting to mock backend."""
        config = {"world_name": "TestWorld", "simulate_events": False}

        success = await backend.connect(config)
        assert success is True
        assert backend.is_connected is True
        assert backend.environment_state.world_name == "TestWorld"

    @pytest.mark.asyncio
    async def test_disconnect(self, backend):
        """Test disconnecting from mock backend."""
        await backend.connect({})
        assert backend.is_connected is True

        await backend.disconnect()
        assert backend.is_connected is False

    @pytest.mark.asyncio
    async def test_send_animation(self, backend):
        """Test sending animation data."""
        await backend.connect({})

        anim = CanonicalAnimationData(timestamp=1.0, emotion=EmotionType.HAPPY, gesture=GestureType.WAVE)

        success = await backend.send_animation_data(anim)
        assert success is True
        assert backend.current_animation == anim
        assert len(backend.animation_history) == 1

    @pytest.mark.asyncio
    async def test_send_audio(self, backend):
        """Test sending audio data."""
        await backend.connect({})

        audio = AudioData(data=b"test_audio", format="mp3", duration=2.5, text="Hello world")

        success = await backend.send_audio_data(audio)
        assert success is True
        assert backend.current_audio == audio
        assert len(backend.audio_history) == 1

    @pytest.mark.asyncio
    async def test_receive_state(self, backend):
        """Test receiving environment state."""
        await backend.connect({"world_name": "TestWorld"})

        state = await backend.receive_state()
        assert state is not None
        assert state.world_name == "TestWorld"
        assert state.agent_position is not None

    @pytest.mark.asyncio
    async def test_capture_video_frame(self, backend):
        """Test capturing video frame."""
        await backend.connect({})

        frame = await backend.capture_video_frame()
        assert frame is not None
        assert frame.width == 640
        assert frame.height == 480
        assert frame.format == "jpeg"
        assert frame.frame_number == 0

        # Capture another frame
        frame2 = await backend.capture_video_frame()
        assert frame2.frame_number == 1

    @pytest.mark.asyncio
    async def test_set_environment(self, backend):
        """Test changing environment."""
        await backend.connect({})

        success = await backend.set_environment("NewWorld", x=10.0, y=0.0, z=5.0)
        assert success is True
        assert backend.environment_state.world_name == "NewWorld"
        assert backend.environment_state.agent_position.x == 10.0
        assert backend.environment_state.agent_position.z == 5.0

    @pytest.mark.asyncio
    async def test_execute_behavior(self, backend):
        """Test executing behavior."""
        await backend.connect({})

        success = await backend.execute_behavior("greet", {"target": "user123"})
        assert success is True
        assert len(backend.animation_history) == 1

        # Check that greet behavior created appropriate animation
        anim = backend.animation_history[0]
        assert anim.gesture == GestureType.WAVE
        assert anim.emotion == EmotionType.HAPPY

    @pytest.mark.asyncio
    async def test_event_handling(self, backend):
        """Test event handler registration and emission."""
        await backend.connect({})

        # Track events
        events_received = []

        async def event_handler(data):
            events_received.append(data)

        # Register handler
        backend.register_event_handler("test_event", event_handler)

        # Emit event
        await backend._emit_event("test_event", {"message": "test"})

        # Allow event to process
        await asyncio.sleep(0.01)

        assert len(events_received) == 1
        assert events_received[0]["message"] == "test"

    @pytest.mark.asyncio
    async def test_health_check(self, backend):
        """Test health check."""
        await backend.connect({})

        health = await backend.health_check()
        assert health["backend"] == "mock"
        assert health["connected"] is True
        assert health["capabilities"]["animation"] is True
        assert health["capabilities"]["video_capture"] is True

    @pytest.mark.asyncio
    async def test_statistics(self, backend):
        """Test getting statistics."""
        await backend.connect({})

        # Send some data
        await backend.send_animation_data(CanonicalAnimationData(timestamp=1.0))
        await backend.send_animation_data(CanonicalAnimationData(timestamp=2.0))
        await backend.capture_video_frame()

        stats = await backend.get_statistics()
        assert stats["backend"] == "mock"
        assert stats["frames_sent"] == 2
        assert stats["frames_captured"] == 1
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_animation_history(self, backend):
        """Test animation history tracking."""
        await backend.connect({})

        # Send multiple animations
        for i in range(3):
            anim = CanonicalAnimationData(timestamp=float(i), emotion=EmotionType.HAPPY if i % 2 == 0 else EmotionType.SAD)
            await backend.send_animation_data(anim)

        history = backend.get_animation_history()
        assert len(history) == 3
        assert history[0]["timestamp"] == 0.0
        assert history[0]["emotion"] == "happy"
        assert history[1]["emotion"] == "sad"

    @pytest.mark.asyncio
    async def test_clear_history(self, backend):
        """Test clearing history."""
        await backend.connect({})

        # Add some data
        await backend.send_animation_data(CanonicalAnimationData(timestamp=1.0))
        await backend.capture_video_frame()

        assert len(backend.animation_history) == 1
        assert backend.frame_counter == 1

        # Clear history
        backend.clear_history()

        assert len(backend.animation_history) == 0
        assert len(backend.audio_history) == 0
        assert backend.frame_counter == 0

    @pytest.mark.asyncio
    async def test_not_connected_operations(self, backend):
        """Test operations when not connected."""
        # Try operations without connecting
        assert backend.is_connected is False

        success = await backend.send_animation_data(CanonicalAnimationData(timestamp=1.0))
        assert success is False

        success = await backend.send_audio_data(AudioData(data=b"test"))
        assert success is False

        state = await backend.receive_state()
        assert state is None

        frame = await backend.capture_video_frame()
        assert frame is None
