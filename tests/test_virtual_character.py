"""Unit tests for Virtual Character MCP Server core components.

Tests cover:
- AudioValidator: Audio format detection and validation
- AudioPathValidator: Path validation and resolution
- AudioHandler: Audio input processing
- SequenceHandler: Event sequence management
"""

import base64
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import modules under test
from tools.mcp.mcp_virtual_character.mcp_virtual_character.audio_handler import (
    AudioDownloader,
    AudioHandler,
    AudioPathValidator,
    AudioPlayer,
    AudioValidator,
)
from tools.mcp.mcp_virtual_character.mcp_virtual_character.models.canonical import (
    EventType,
)
from tools.mcp.mcp_virtual_character.mcp_virtual_character.sequence_handler import (
    SequenceHandler,
)

# =============================================================================
# AudioValidator Tests
# =============================================================================


class TestAudioValidator:
    """Tests for AudioValidator class."""

    def test_detect_format_mp3_id3(self):
        """Test detection of MP3 with ID3v2 tag."""
        data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 100
        assert AudioValidator.detect_format(data) == "mp3"

    def test_detect_format_mp3_mpeg1(self):
        """Test detection of MPEG-1 Layer 3."""
        data = b"\xff\xfb\x90\x00" + b"\x00" * 100
        assert AudioValidator.detect_format(data) == "mp3"

    def test_detect_format_mp3_mpeg2(self):
        """Test detection of MPEG-2 Layer 3."""
        data = b"\xff\xf3\x90\x00" + b"\x00" * 100
        assert AudioValidator.detect_format(data) == "mp3"

    def test_detect_format_wav(self):
        """Test detection of WAV format."""
        data = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
        assert AudioValidator.detect_format(data) == "wav"

    def test_detect_format_ogg(self):
        """Test detection of Ogg format."""
        data = b"OggS\x00\x02\x00\x00" + b"\x00" * 100
        assert AudioValidator.detect_format(data) == "ogg"

    def test_detect_format_flac(self):
        """Test detection of FLAC format."""
        data = b"fLaC\x00\x00\x00\x22" + b"\x00" * 100
        assert AudioValidator.detect_format(data) == "flac"

    def test_detect_format_unknown(self):
        """Test unknown format returns None."""
        data = b"\x00\x00\x00\x00" + b"\x00" * 100
        assert AudioValidator.detect_format(data) is None

    def test_is_valid_audio_too_small(self):
        """Test rejection of too-small audio."""
        data = b"\xff\xfb" * 10  # Less than MIN_AUDIO_SIZE
        is_valid, msg = AudioValidator.is_valid_audio(data)
        assert not is_valid
        assert "too small" in msg.lower()

    def test_is_valid_audio_html_detection(self):
        """Test rejection of HTML content."""
        data = b"<!DOCTYPE html>" + b"\x00" * 100
        is_valid, msg = AudioValidator.is_valid_audio(data)
        assert not is_valid
        assert "HTML" in msg

    def test_is_valid_audio_html_detection_case_insensitive(self):
        """Test HTML detection is case-insensitive."""
        data = b"<HTML>" + b"\x00" * 100
        is_valid, msg = AudioValidator.is_valid_audio(data)
        assert not is_valid
        assert "HTML" in msg

    def test_is_valid_audio_valid_mp3(self):
        """Test acceptance of valid MP3."""
        data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 200
        is_valid, msg = AudioValidator.is_valid_audio(data)
        assert is_valid
        assert "mp3" in msg.lower()

    def test_is_valid_audio_unknown_but_large(self):
        """Test acceptance of unknown format if large enough."""
        # Unknown signature but large enough
        data = b"\x00\x01\x02\x03" + b"\x00" * 2000
        is_valid, msg = AudioValidator.is_valid_audio(data)
        assert is_valid
        assert "unknown" in msg.lower()

    def test_is_valid_audio_unknown_and_small(self):
        """Test rejection of unknown format if too small."""
        # Unknown signature and small
        data = b"\x00\x01\x02\x03" + b"\x00" * 200  # Larger than MIN but less than MIN*10
        is_valid, msg = AudioValidator.is_valid_audio(data)
        assert not is_valid


# =============================================================================
# AudioPathValidator Tests
# =============================================================================


class TestAudioPathValidator:
    """Tests for AudioPathValidator class."""

    def test_is_path_allowed_tmp(self):
        """Test /tmp path is allowed."""
        validator = AudioPathValidator()
        # Create a real temp file to test
        with tempfile.NamedTemporaryFile(dir="/tmp", delete=False) as f:
            path = Path(f.name)
            assert validator.is_path_allowed(path)

    def test_is_path_allowed_disallowed(self):
        """Test disallowed paths are rejected."""
        validator = AudioPathValidator()
        assert not validator.is_path_allowed(Path("/etc/passwd"))
        assert not validator.is_path_allowed(Path("/root/.bashrc"))

    def test_is_path_allowed_custom_paths(self):
        """Test custom allowed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir)
            validator = AudioPathValidator(additional_allowed_paths=[custom_path])
            test_file = custom_path / "test.mp3"
            test_file.touch()
            assert validator.is_path_allowed(test_file)

    def test_resolve_audio_path_existing_file(self):
        """Test resolution of existing file."""
        validator = AudioPathValidator()
        with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".mp3", delete=False) as f:
            path, error = validator.resolve_audio_path(f.name)
            assert path is not None
            assert error is None
            assert path.exists()

    def test_resolve_audio_path_nonexistent(self):
        """Test resolution of non-existent file."""
        validator = AudioPathValidator()
        path, error = validator.resolve_audio_path("/tmp/nonexistent_file_12345.mp3")
        assert path is None
        assert error is not None
        assert "not found" in error.lower()


# =============================================================================
# AudioHandler Tests
# =============================================================================


class TestAudioHandler:
    """Tests for AudioHandler class."""

    def test_decode_base64_valid(self):
        """Test decoding valid base64 audio."""
        handler = AudioHandler()
        # Valid MP3 header encoded
        mp3_data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 200
        encoded = base64.b64encode(mp3_data).decode()

        result, error = handler._decode_base64(encoded)
        assert result is not None
        assert error is None
        assert result == mp3_data

    def test_decode_base64_invalid(self):
        """Test decoding invalid base64."""
        handler = AudioHandler()
        result, error = handler._decode_base64("not valid base64!!!")
        assert result is None
        assert error is not None
        assert "Invalid base64" in error

    def test_decode_data_url_valid(self):
        """Test decoding valid data URL."""
        handler = AudioHandler()
        mp3_data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 200
        encoded = base64.b64encode(mp3_data).decode()
        data_url = f"data:audio/mp3;base64,{encoded}"

        result, error = handler._decode_data_url(data_url)
        assert result is not None
        assert error is None
        assert result == mp3_data

    def test_decode_data_url_invalid(self):
        """Test decoding invalid data URL."""
        handler = AudioHandler()
        result, error = handler._decode_data_url("invalid data url")
        assert result is None
        assert error is not None

    def test_read_from_file_valid(self):
        """Test reading from valid file."""
        handler = AudioHandler()
        mp3_data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 200

        with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".mp3", delete=False) as f:
            f.write(mp3_data)
            f.flush()

            result, error = handler._read_from_file(f.name)
            assert result is not None
            assert error is None
            assert result == mp3_data

    def test_read_from_file_disallowed_path(self):
        """Test reading from disallowed path."""
        handler = AudioHandler()
        result, error = handler._read_from_file("/etc/passwd")
        assert result is None
        assert error is not None

    @pytest.mark.asyncio
    async def test_process_audio_input_base64(self):
        """Test processing base64 audio input."""
        handler = AudioHandler()
        mp3_data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 200
        encoded = base64.b64encode(mp3_data).decode()

        result, error = await handler.process_audio_input(encoded)
        assert result is not None
        assert error is None

    @pytest.mark.asyncio
    async def test_process_audio_input_data_url(self):
        """Test processing data URL audio input."""
        handler = AudioHandler()
        mp3_data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 200
        encoded = base64.b64encode(mp3_data).decode()
        data_url = f"data:audio/mp3;base64,{encoded}"

        result, error = await handler.process_audio_input(data_url)
        assert result is not None
        assert error is None

    @pytest.mark.asyncio
    async def test_process_audio_input_file_path(self):
        """Test processing file path audio input."""
        handler = AudioHandler()
        mp3_data = b"ID3\x04\x00\x00\x00\x00" + b"\x00" * 200

        with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".mp3", delete=False) as f:
            f.write(mp3_data)
            f.flush()

            result, error = await handler.process_audio_input(f.name)
            assert result is not None
            assert error is None


# =============================================================================
# AudioDownloader Tests
# =============================================================================


class TestAudioDownloader:
    """Tests for AudioDownloader class."""

    @pytest.mark.asyncio
    async def test_download_invalid_url(self):
        """Test download with invalid/unreachable URL."""
        downloader = AudioDownloader()

        # Test with a URL that won't resolve (connection error)
        result, error = await downloader.download("http://invalid-host-that-does-not-exist.test/audio.mp3")
        assert result is None
        assert error is not None
        # Should get a connection error
        assert "error" in error.lower()


# =============================================================================
# AudioPlayer Tests
# =============================================================================


class TestAudioPlayer:
    """Tests for AudioPlayer class."""

    @pytest.mark.asyncio
    async def test_run_subprocess_success(self):
        """Test successful subprocess execution."""
        player = AudioPlayer()
        return_code, stdout, stderr = await player._run_subprocess(
            ["echo", "hello"],
            timeout=5.0,
        )
        assert return_code == 0
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_run_subprocess_file_not_found(self):
        """Test subprocess with non-existent command."""
        player = AudioPlayer()
        with pytest.raises(FileNotFoundError):
            await player._run_subprocess(
                ["nonexistent_command_12345"],
                timeout=5.0,
            )

    @pytest.mark.asyncio
    async def test_start_subprocess_detached_success(self):
        """Test detached subprocess start."""
        player = AudioPlayer()
        result = await player._start_subprocess_detached(["sleep", "0.1"])
        assert result is True

    @pytest.mark.asyncio
    async def test_start_subprocess_detached_not_found(self):
        """Test detached subprocess with non-existent command."""
        player = AudioPlayer()
        result = await player._start_subprocess_detached(["nonexistent_command_12345"])
        assert result is False


# =============================================================================
# SequenceHandler Tests
# =============================================================================


class TestSequenceHandler:
    """Tests for SequenceHandler class."""

    @pytest.mark.asyncio
    async def test_create_sequence(self):
        """Test sequence creation."""
        handler = SequenceHandler()
        result = await handler.create_sequence("test_sequence", description="Test")

        assert result["success"] is True
        assert handler.current_sequence is not None
        assert handler.current_sequence.name == "test_sequence"

    @pytest.mark.asyncio
    async def test_add_event_no_sequence(self):
        """Test adding event without sequence."""
        handler = SequenceHandler()
        result = await handler.add_event(event_type="animation", timestamp=0.0)

        assert result["success"] is False
        assert "No sequence created" in result["error"]

    @pytest.mark.asyncio
    async def test_add_animation_event(self):
        """Test adding animation event."""
        handler = SequenceHandler()
        await handler.create_sequence("test")

        result = await handler.add_event(
            event_type="animation",
            timestamp=1.0,
            animation_params={"emotion": "happy", "gesture": "wave"},
        )

        assert result["success"] is True
        assert len(handler.current_sequence.events) == 1

    @pytest.mark.asyncio
    async def test_add_expression_event(self):
        """Test adding expression event."""
        handler = SequenceHandler()
        await handler.create_sequence("test")

        result = await handler.add_event(
            event_type="expression",
            timestamp=0.5,
            expression="happy",
            expression_intensity=0.8,
        )

        assert result["success"] is True
        assert len(handler.current_sequence.events) == 1

    @pytest.mark.asyncio
    async def test_add_wait_event(self):
        """Test adding wait event."""
        handler = SequenceHandler()
        await handler.create_sequence("test")

        result = await handler.add_event(
            event_type="wait",
            timestamp=0.0,
            wait_duration=2.0,
        )

        assert result["success"] is True
        event = handler.current_sequence.events[0]
        assert event.event_type == EventType.WAIT
        assert event.wait_duration == 2.0

    @pytest.mark.asyncio
    async def test_add_movement_event(self):
        """Test adding movement event."""
        handler = SequenceHandler()
        await handler.create_sequence("test")

        result = await handler.add_event(
            event_type="movement",
            timestamp=1.0,
            movement_params={"move_forward": 1.0, "duration": 2.0},
        )

        assert result["success"] is True
        event = handler.current_sequence.events[0]
        assert event.event_type == EventType.MOVEMENT

    @pytest.mark.asyncio
    async def test_add_parallel_events(self):
        """Test adding parallel events."""
        handler = SequenceHandler()
        await handler.create_sequence("test")

        result = await handler.add_event(
            event_type="parallel",
            timestamp=0.0,
            parallel_events=[
                {"event_type": "expression", "timestamp": 0.0, "expression": "happy"},
                {"event_type": "wait", "timestamp": 0.0, "wait_duration": 1.0},
            ],
        )

        assert result["success"] is True
        event = handler.current_sequence.events[0]
        assert event.event_type == EventType.PARALLEL
        assert len(event.parallel_events) == 2

    @pytest.mark.asyncio
    async def test_pause_no_sequence(self):
        """Test pause when no sequence playing."""
        handler = SequenceHandler()
        result = await handler.pause_sequence()

        assert result["success"] is False
        assert "No sequence is playing" in result["error"]

    @pytest.mark.asyncio
    async def test_resume_no_sequence(self):
        """Test resume when no sequence."""
        handler = SequenceHandler()
        result = await handler.resume_sequence()

        assert result["success"] is False
        assert "No sequence to resume" in result["error"]

    @pytest.mark.asyncio
    async def test_stop_no_sequence(self):
        """Test stop when no sequence playing."""
        handler = SequenceHandler()
        result = await handler.stop_sequence()

        assert result["success"] is False
        assert "No sequence is playing" in result["error"]

    @pytest.mark.asyncio
    async def test_get_status_empty(self):
        """Test status when no sequence."""
        handler = SequenceHandler()
        result = await handler.get_status()

        assert result["success"] is True
        assert result["status"]["has_sequence"] is False
        assert result["status"]["is_playing"] is False

    @pytest.mark.asyncio
    async def test_get_status_with_sequence(self):
        """Test status with sequence."""
        handler = SequenceHandler()
        await handler.create_sequence("test", description="Test sequence")
        await handler.add_event(event_type="wait", timestamp=0.0, wait_duration=1.0)

        result = await handler.get_status()

        assert result["success"] is True
        assert result["status"]["has_sequence"] is True
        assert result["status"]["sequence_name"] == "test"
        assert result["status"]["event_count"] == 1

    @pytest.mark.asyncio
    async def test_panic_reset(self):
        """Test panic reset."""
        handler = SequenceHandler()
        await handler.create_sequence("test")
        await handler.add_event(event_type="wait", timestamp=0.0, wait_duration=1.0)

        # Create mock backend
        mock_backend = AsyncMock()

        result = await handler.panic_reset(mock_backend)

        assert result["success"] is True
        assert handler.current_sequence is None
        assert handler.sequence_paused is False
        mock_backend.send_animation_data.assert_called()

    @pytest.mark.asyncio
    async def test_play_sequence_no_backend(self):
        """Test play without backend."""
        handler = SequenceHandler()
        await handler.create_sequence("test")

        result = await handler.play_sequence(backend=None)

        assert result["success"] is False
        assert "No backend connected" in result["error"]

    @pytest.mark.asyncio
    async def test_play_sequence_no_sequence(self):
        """Test play without sequence."""
        handler = SequenceHandler()
        mock_backend = AsyncMock()

        result = await handler.play_sequence(backend=mock_backend)

        assert result["success"] is False
        assert "No sequence to play" in result["error"]

    @pytest.mark.asyncio
    async def test_create_event_from_dict_invalid_type(self):
        """Test creating event with invalid type."""
        handler = SequenceHandler()
        result = await handler._create_event_from_dict({"event_type": "invalid_type"})
        assert result is None

    @pytest.mark.asyncio
    async def test_sequence_loop_flag(self):
        """Test sequence loop flag is set."""
        handler = SequenceHandler()
        await handler.create_sequence("test", loop=True)

        assert handler.current_sequence.loop is True

    @pytest.mark.asyncio
    async def test_sequence_interrupt_current(self):
        """Test interrupt_current stops existing sequence."""
        handler = SequenceHandler()

        # Create first sequence
        await handler.create_sequence("first")

        # Create mock task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()
        handler.sequence_task = mock_task

        # Create second sequence with interrupt
        with patch.object(handler, "_cancel_running_sequence", new_callable=AsyncMock) as mock_cancel:
            await handler.create_sequence("second", interrupt_current=True)
            mock_cancel.assert_called_once()
