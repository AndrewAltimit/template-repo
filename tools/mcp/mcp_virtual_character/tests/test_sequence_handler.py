"""Pytest tests for the Virtual Character Sequence Handler.

These tests verify:
- Sequence creation and management
- Event addition and validation
- Playback control (play, pause, resume, stop)
- Async task handling and cancellation
- Error handling and edge cases
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from tools.mcp.mcp_virtual_character.mcp_virtual_character.sequence_handler import SequenceHandler


@pytest.fixture
def sequence_handler():
    """Create a fresh sequence handler for each test."""
    return SequenceHandler()


@pytest.fixture
def mock_backend():
    """Create a mock backend adapter."""
    backend = AsyncMock()
    backend.send_animation_data = AsyncMock(return_value=True)
    backend.send_audio_data = AsyncMock(return_value=True)
    backend.connected = True
    return backend


class TestSequenceCreation:
    """Test sequence creation functionality."""

    @pytest.mark.asyncio
    async def test_create_sequence_basic(self, sequence_handler):
        """Test basic sequence creation."""
        result = await sequence_handler.create_sequence(name="test_sequence")

        assert result["success"] is True
        assert "test_sequence" in result["message"]
        assert sequence_handler.current_sequence is not None
        assert sequence_handler.current_sequence.name == "test_sequence"

    @pytest.mark.asyncio
    async def test_create_sequence_with_options(self, sequence_handler):
        """Test sequence creation with all options."""
        result = await sequence_handler.create_sequence(
            name="detailed_sequence",
            description="A test sequence with description",
            loop=True,
            interrupt_current=False,
        )

        assert result["success"] is True
        assert sequence_handler.current_sequence.name == "detailed_sequence"
        assert sequence_handler.current_sequence.description == "A test sequence with description"
        assert sequence_handler.current_sequence.loop is True
        assert sequence_handler.current_sequence.interrupt_current is False

    @pytest.mark.asyncio
    async def test_create_sequence_replaces_existing(self, sequence_handler):
        """Test that creating a new sequence replaces the existing one."""
        await sequence_handler.create_sequence(name="first_sequence")
        await sequence_handler.create_sequence(name="second_sequence")

        assert sequence_handler.current_sequence.name == "second_sequence"


class TestEventAddition:
    """Test adding events to sequences."""

    @pytest.mark.asyncio
    async def test_add_event_no_sequence(self, sequence_handler):
        """Test adding event without creating sequence first."""
        result = await sequence_handler.add_event(event_type="animation", timestamp=0.0)

        assert result["success"] is False
        assert "No sequence created" in result["error"]

    @pytest.mark.asyncio
    async def test_add_animation_event(self, sequence_handler):
        """Test adding an animation event."""
        await sequence_handler.create_sequence(name="test")

        result = await sequence_handler.add_event(
            event_type="animation",
            timestamp=1.0,
            duration=2.0,
            animation_params={"emotion": "happy", "emotion_intensity": 0.8},
        )

        assert result["success"] is True
        assert len(sequence_handler.current_sequence.events) == 1

    @pytest.mark.asyncio
    async def test_add_wait_event(self, sequence_handler):
        """Test adding a wait event."""
        await sequence_handler.create_sequence(name="test")

        result = await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=5.0)

        assert result["success"] is True
        assert len(sequence_handler.current_sequence.events) == 1

    @pytest.mark.asyncio
    async def test_add_expression_event(self, sequence_handler):
        """Test adding an expression event."""
        await sequence_handler.create_sequence(name="test")

        result = await sequence_handler.add_event(
            event_type="expression", timestamp=0.5, expression="happy", expression_intensity=0.9
        )

        assert result["success"] is True
        assert len(sequence_handler.current_sequence.events) == 1

    @pytest.mark.asyncio
    async def test_add_multiple_events(self, sequence_handler):
        """Test adding multiple events to a sequence."""
        await sequence_handler.create_sequence(name="multi_event")

        await sequence_handler.add_event(event_type="expression", timestamp=0.0, expression="neutral")
        await sequence_handler.add_event(event_type="wait", timestamp=1.0, wait_duration=2.0)
        await sequence_handler.add_event(event_type="expression", timestamp=3.0, expression="happy")

        assert len(sequence_handler.current_sequence.events) == 3

    @pytest.mark.asyncio
    async def test_add_invalid_event_type(self, sequence_handler):
        """Test adding an event with invalid type."""
        await sequence_handler.create_sequence(name="test")

        result = await sequence_handler.add_event(event_type="invalid_type", timestamp=0.0)

        assert result["success"] is False


class TestPlaybackControl:
    """Test sequence playback controls."""

    @pytest.mark.asyncio
    async def test_play_sequence_no_backend(self, sequence_handler):
        """Test playing without backend connected."""
        await sequence_handler.create_sequence(name="test")

        result = await sequence_handler.play_sequence(backend=None)

        assert result["success"] is False
        assert "No backend" in result["error"]

    @pytest.mark.asyncio
    async def test_play_sequence_no_sequence(self, sequence_handler, mock_backend):
        """Test playing without creating sequence."""
        result = await sequence_handler.play_sequence(backend=mock_backend)

        assert result["success"] is False
        assert "No sequence" in result["error"]

    @pytest.mark.asyncio
    async def test_play_sequence_basic(self, sequence_handler, mock_backend):
        """Test basic sequence playback."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=0.1)

        result = await sequence_handler.play_sequence(backend=mock_backend)

        assert result["success"] is True
        assert sequence_handler.sequence_task is not None

        # Wait for sequence to complete
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_pause_no_sequence(self, sequence_handler):
        """Test pausing when no sequence is playing."""
        result = await sequence_handler.pause_sequence()

        assert result["success"] is False
        assert "No sequence is playing" in result["error"]

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, sequence_handler, mock_backend):
        """Test pause and resume functionality."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=2.0)
        await sequence_handler.play_sequence(backend=mock_backend)

        # Wait a moment then pause
        await asyncio.sleep(0.1)

        pause_result = await sequence_handler.pause_sequence()
        assert pause_result["success"] is True
        assert sequence_handler.sequence_paused is True

        resume_result = await sequence_handler.resume_sequence()
        assert resume_result["success"] is True
        assert sequence_handler.sequence_paused is False

        # Clean up
        await sequence_handler.stop_sequence()

    @pytest.mark.asyncio
    async def test_stop_sequence(self, sequence_handler, mock_backend):
        """Test stopping a running sequence."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=10.0)
        await sequence_handler.play_sequence(backend=mock_backend)

        await asyncio.sleep(0.1)

        result = await sequence_handler.stop_sequence()

        assert result["success"] is True
        assert sequence_handler.sequence_task is None or sequence_handler.sequence_task.done()


class TestSequenceStatus:
    """Test sequence status retrieval."""

    @pytest.mark.asyncio
    async def test_get_status_no_sequence(self, sequence_handler):
        """Test status when no sequence exists."""
        result = await sequence_handler.get_status()

        assert result["success"] is True
        assert result["status"]["has_sequence"] is False
        assert result["status"]["is_playing"] is False

    @pytest.mark.asyncio
    async def test_get_status_with_sequence(self, sequence_handler):
        """Test status with sequence created."""
        await sequence_handler.create_sequence(name="status_test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=1.0)

        result = await sequence_handler.get_status()

        assert result["success"] is True
        assert result["status"]["has_sequence"] is True
        assert result["status"]["sequence_name"] == "status_test"
        assert result["status"]["event_count"] == 1

    @pytest.mark.asyncio
    async def test_get_status_while_playing(self, sequence_handler, mock_backend):
        """Test status while sequence is playing."""
        await sequence_handler.create_sequence(name="playing_test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=5.0)
        await sequence_handler.play_sequence(backend=mock_backend)

        await asyncio.sleep(0.1)

        result = await sequence_handler.get_status()

        assert result["success"] is True
        assert result["status"]["is_playing"] is True

        # Clean up
        await sequence_handler.stop_sequence()


class TestPanicReset:
    """Test emergency reset functionality."""

    @pytest.mark.asyncio
    async def test_panic_reset_no_backend(self, sequence_handler):
        """Test panic reset without backend."""
        await sequence_handler.create_sequence(name="test")

        result = await sequence_handler.panic_reset(backend=None)

        assert result["success"] is True
        assert sequence_handler.current_sequence is None
        assert sequence_handler.sequence_paused is False

    @pytest.mark.asyncio
    async def test_panic_reset_with_playing_sequence(self, sequence_handler, mock_backend):
        """Test panic reset while sequence is playing."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=10.0)
        await sequence_handler.play_sequence(backend=mock_backend)

        await asyncio.sleep(0.1)

        result = await sequence_handler.panic_reset(backend=mock_backend)

        assert result["success"] is True
        assert sequence_handler.current_sequence is None
        assert sequence_handler.sequence_task is None or sequence_handler.sequence_task.done()


class TestEventExecution:
    """Test event execution during playback."""

    @pytest.mark.asyncio
    async def test_animation_event_calls_backend(self, sequence_handler, mock_backend):
        """Test that animation events call backend."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(
            event_type="animation", timestamp=0.0, animation_params={"emotion": "happy", "emotion_intensity": 1.0}
        )

        await sequence_handler.play_sequence(backend=mock_backend)

        # Wait for execution
        await asyncio.sleep(0.3)

        # Backend should have been called
        mock_backend.send_animation_data.assert_called()

    @pytest.mark.asyncio
    async def test_expression_event_calls_backend(self, sequence_handler, mock_backend):
        """Test that expression events call backend."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(event_type="expression", timestamp=0.0, expression="happy")

        await sequence_handler.play_sequence(backend=mock_backend)
        await asyncio.sleep(0.3)

        mock_backend.send_animation_data.assert_called()


class TestAsyncTaskHandling:
    """Test proper handling of async tasks."""

    @pytest.mark.asyncio
    async def test_sequence_task_properly_cancelled(self, sequence_handler, mock_backend):
        """Test that sequence task is properly cancelled and awaited."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=30.0)
        await sequence_handler.play_sequence(backend=mock_backend)

        await asyncio.sleep(0.1)
        assert sequence_handler.sequence_task is not None
        assert not sequence_handler.sequence_task.done()

        # Stop should properly cancel and await the task
        await sequence_handler.stop_sequence()

        # Task should be cancelled now
        assert sequence_handler.sequence_task is None or sequence_handler.sequence_task.done()

    @pytest.mark.asyncio
    async def test_multiple_play_calls_cancel_previous(self, sequence_handler, mock_backend):
        """Test that calling play multiple times cancels previous sequence."""
        await sequence_handler.create_sequence(name="first")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=30.0)
        await sequence_handler.play_sequence(backend=mock_backend)

        first_task = sequence_handler.sequence_task
        await asyncio.sleep(0.1)

        # Create and play new sequence
        await sequence_handler.create_sequence(name="second")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=0.1)
        await sequence_handler.play_sequence(backend=mock_backend)

        # First task should be cancelled
        assert first_task.cancelled() or first_task.done()

        # Clean up
        await sequence_handler.stop_sequence()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_sequence_playback(self, sequence_handler, mock_backend):
        """Test playing a sequence with no events."""
        await sequence_handler.create_sequence(name="empty")

        result = await sequence_handler.play_sequence(backend=mock_backend)

        assert result["success"] is True

        # Should complete quickly
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_resume_without_pause(self, sequence_handler, mock_backend):
        """Test resuming when not paused."""
        await sequence_handler.create_sequence(name="test")
        await sequence_handler.add_event(event_type="wait", timestamp=0.0, wait_duration=1.0)
        await sequence_handler.play_sequence(backend=mock_backend)

        await asyncio.sleep(0.1)

        # Resume without pausing first - should still succeed
        result = await sequence_handler.resume_sequence()
        assert result["success"] is True

        await sequence_handler.stop_sequence()

    @pytest.mark.asyncio
    async def test_stop_when_not_playing(self, sequence_handler):
        """Test stopping when no sequence is playing."""
        result = await sequence_handler.stop_sequence()

        assert result["success"] is False
        assert "No sequence is playing" in result["error"]
