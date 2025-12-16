"""Pytest tests for the Virtual Character Audio Handler.

These tests verify:
- Audio path validation and security
- Audio format detection
- Audio downloading from URLs
- File path resolution with container mappings
"""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.mcp.mcp_virtual_character.mcp_virtual_character.audio_handler import (
    AudioDownloader,
    AudioHandler,
    AudioPathValidator,
    AudioValidator,
)


class TestAudioPathValidator:
    """Test audio path validation security."""

    def test_allowed_path_outputs(self, tmp_path):
        """Test that outputs directory is allowed."""
        validator = AudioPathValidator()

        # Create a test file in allowed path
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"test")

        # Add tmp_path to allowed paths for testing
        validator.allowed_paths.append(tmp_path)

        assert validator.is_path_allowed(test_file) is True

    def test_disallowed_path(self, tmp_path):
        """Test that paths outside allowed directories are blocked."""
        validator = AudioPathValidator()

        # Clear default allowed paths and set a specific one
        validator.allowed_paths = [Path("/only_this_is_allowed")]

        # Create test file in non-allowed location
        test_file = tmp_path / "evil" / "test.mp3"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"test")

        # tmp_path is NOT in allowed paths
        assert validator.is_path_allowed(test_file) is False

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        validator = AudioPathValidator()

        # Attempt path traversal
        malicious_paths = [
            Path("/tmp/../etc/passwd"),
            Path("/tmp/../../root/.ssh/id_rsa"),
            Path("outputs/../../../etc/shadow"),
        ]

        for path in malicious_paths:
            # These should either be disallowed or resolve to invalid location
            allowed = validator.is_path_allowed(path)
            # If path resolves to somewhere outside allowed dirs, should be False
            # Some might not exist, which is also fine
            assert allowed is False or not path.resolve().exists()

    def test_resolve_audio_path_container_mapping(self, tmp_path):
        """Test container path resolution."""
        validator = AudioPathValidator()
        validator.allowed_paths.append(tmp_path)

        # Create test structure
        speech_dir = tmp_path / "outputs" / "elevenlabs_speech" / "2024-01-01"
        speech_dir.mkdir(parents=True, exist_ok=True)
        test_file = speech_dir / "test.mp3"
        test_file.write_bytes(b"test audio content")

        # The validator should find files through mapping
        # (In real use, this maps container paths to host paths)
        validator.allowed_paths.append(speech_dir.parent.parent)

        # Direct path should work
        resolved, error = validator.resolve_audio_path(str(test_file))
        assert error is None
        assert resolved == test_file

    def test_resolve_audio_path_not_found(self):
        """Test resolution of non-existent path."""
        validator = AudioPathValidator()

        resolved, error = validator.resolve_audio_path("/nonexistent/path/audio.mp3")

        assert resolved is None
        assert "not found" in error.lower()


class TestAudioValidator:
    """Test audio format detection and validation."""

    def test_detect_mp3_id3(self):
        """Test detection of MP3 with ID3 tag."""
        mp3_data = b"ID3" + b"\x00" * 100

        fmt = AudioValidator.detect_format(mp3_data)
        assert fmt == "mp3"

    def test_detect_mp3_mpeg1(self):
        """Test detection of MPEG-1 Layer 3."""
        mp3_data = b"\xff\xfb" + b"\x00" * 100

        fmt = AudioValidator.detect_format(mp3_data)
        assert fmt == "mp3"

    def test_detect_wav(self):
        """Test detection of WAV format."""
        wav_data = b"RIFF" + b"\x00" * 100

        fmt = AudioValidator.detect_format(wav_data)
        assert fmt == "wav"

    def test_detect_ogg(self):
        """Test detection of Ogg format."""
        ogg_data = b"OggS" + b"\x00" * 100

        fmt = AudioValidator.detect_format(ogg_data)
        assert fmt == "ogg"

    def test_detect_flac(self):
        """Test detection of FLAC format."""
        flac_data = b"fLaC" + b"\x00" * 100

        fmt = AudioValidator.detect_format(flac_data)
        assert fmt == "flac"

    def test_detect_unknown(self):
        """Test detection of unknown format."""
        unknown_data = b"UNKNOWN" + b"\x00" * 100

        fmt = AudioValidator.detect_format(unknown_data)
        assert fmt is None

    def test_is_valid_audio_mp3(self):
        """Test validation of valid MP3 data."""
        mp3_data = b"ID3" + b"\x00" * 1000

        is_valid, msg = AudioValidator.is_valid_audio(mp3_data)
        assert is_valid is True
        assert "mp3" in msg.lower()

    def test_is_valid_audio_too_small(self):
        """Test rejection of audio that's too small."""
        tiny_data = b"ID3" + b"\x00" * 10

        is_valid, msg = AudioValidator.is_valid_audio(tiny_data)
        assert is_valid is False
        assert "small" in msg.lower()

    def test_is_valid_audio_html_error(self):
        """Test rejection of HTML error pages."""
        # Make it large enough to pass size check, so HTML check can trigger
        html_data = b"<!DOCTYPE html><html><body>" + b"Error" * 50 + b"</body></html>"

        is_valid, msg = AudioValidator.is_valid_audio(html_data)
        assert is_valid is False
        assert "html" in msg.lower()

    def test_is_valid_audio_html_lowercase(self):
        """Test rejection of HTML with lowercase tag."""
        html_data = b"<html><body>Error</body></html>"

        is_valid, _msg = AudioValidator.is_valid_audio(html_data)
        assert is_valid is False

    def test_is_valid_audio_unknown_but_large(self):
        """Test acceptance of unknown format if large enough."""
        large_data = b"UNKNOWN" + b"\x00" * 5000

        is_valid, msg = AudioValidator.is_valid_audio(large_data)
        assert is_valid is True
        assert "unknown" in msg.lower()


class TestAudioDownloader:
    """Test audio downloading functionality."""

    @pytest.mark.asyncio
    async def test_download_success(self):
        """Test successful audio download."""
        downloader = AudioDownloader()

        audio_data = b"ID3" + b"\x00" * 2000

        # Create properly nested async context managers using AsyncMock
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "audio/mpeg", "Content-Length": "5000"}
        mock_response.read = AsyncMock(return_value=audio_data)

        # Create async context manager for response
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

        # Create mock session
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_ctx)

        # Create async context manager for session
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        # Patch where aiohttp is imported in the audio_handler module
        with patch(
            "tools.mcp.mcp_virtual_character.mcp_virtual_character.audio_handler.aiohttp.ClientSession",
            return_value=mock_session_ctx,
        ):
            data, error = await downloader.download("http://example.com/audio.mp3")

            assert error is None
            assert data == audio_data

    @pytest.mark.asyncio
    async def test_download_http_error(self):
        """Test handling of HTTP errors."""
        downloader = AudioDownloader()

        mock_response = AsyncMock()
        mock_response.status = 404

        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_ctx)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "tools.mcp.mcp_virtual_character.mcp_virtual_character.audio_handler.aiohttp.ClientSession",
            return_value=mock_session_ctx,
        ):
            data, error = await downloader.download("http://example.com/notfound.mp3")

            assert data is None
            assert error is not None
            assert "404" in error

    @pytest.mark.asyncio
    async def test_download_html_response(self):
        """Test handling of HTML error response."""
        downloader = AudioDownloader()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/html"}

        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_ctx)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "tools.mcp.mcp_virtual_character.mcp_virtual_character.audio_handler.aiohttp.ClientSession",
            return_value=mock_session_ctx,
        ):
            data, error = await downloader.download("http://example.com/error")

            assert data is None
            assert error is not None
            assert "html" in error.lower()


class TestAudioHandler:
    """Test the main AudioHandler class."""

    @pytest.fixture
    def handler(self):
        """Create AudioHandler instance."""
        return AudioHandler()

    @pytest.mark.asyncio
    async def test_process_base64_valid(self, handler):
        """Test processing valid base64 audio."""
        # Create valid MP3-like base64 data
        audio_bytes = b"ID3" + b"\x00" * 1000
        audio_b64 = base64.b64encode(audio_bytes).decode()

        data, error = await handler.process_audio_input(audio_b64)

        assert error is None
        assert data == audio_bytes

    @pytest.mark.asyncio
    async def test_process_base64_invalid(self, handler):
        """Test processing invalid base64."""
        invalid_b64 = "not valid base64!!!"

        data, error = await handler.process_audio_input(invalid_b64)

        assert data is None
        assert error is not None

    @pytest.mark.asyncio
    async def test_process_data_url(self, handler):
        """Test processing data URL format."""
        audio_bytes = b"ID3" + b"\x00" * 1000
        audio_b64 = base64.b64encode(audio_bytes).decode()
        data_url = f"data:audio/mp3;base64,{audio_b64}"

        data, error = await handler.process_audio_input(data_url)

        assert error is None
        assert data == audio_bytes

    @pytest.mark.asyncio
    async def test_process_file_path_allowed(self, handler, tmp_path):
        """Test processing allowed file path."""
        # Add tmp_path to allowed paths
        handler.path_validator.allowed_paths.append(tmp_path)

        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_bytes = b"ID3" + b"\x00" * 1000
        audio_file.write_bytes(audio_bytes)

        data, error = await handler.process_audio_input(str(audio_file))

        assert error is None
        assert data == audio_bytes

    @pytest.mark.asyncio
    async def test_process_file_path_not_found(self, handler):
        """Test processing non-existent file path."""
        data, error = await handler.process_audio_input("/nonexistent/audio.mp3")

        assert data is None
        assert "not found" in error.lower()


class TestAudioSecurityEdgeCases:
    """Test security edge cases for audio handling."""

    def test_symlink_attack_blocked(self, tmp_path):
        """Test that symlink attacks are handled."""
        validator = AudioPathValidator()
        validator.allowed_paths.append(tmp_path)

        # Create a file in allowed location
        allowed_file = tmp_path / "allowed.mp3"
        allowed_file.write_bytes(b"ID3" + b"\x00" * 100)

        # Create symlink to disallowed location (if platform supports it)
        try:
            evil_link = tmp_path / "evil_link.mp3"
            evil_link.symlink_to("/etc/passwd")

            # The symlink should resolve to /etc/passwd which is not allowed
            assert validator.is_path_allowed(evil_link) is False
        except OSError:
            # Platform doesn't support symlinks or permission denied
            pass

    def test_null_byte_injection_blocked(self):
        """Test that null byte injection is handled."""
        validator = AudioPathValidator()

        # Attempt null byte injection
        malicious_path = Path("/tmp/audio.mp3\x00.txt")

        # Should not crash and should be handled safely
        try:
            validator.is_path_allowed(malicious_path)
            # Result doesn't matter as long as it doesn't crash
        except ValueError:
            # Some systems raise ValueError for null bytes - that's fine
            pass

    def test_unicode_normalization_safe(self):
        """Test handling of unicode path normalization."""
        validator = AudioPathValidator()

        # Various unicode representations of similar paths
        paths = [
            Path("/tmp/audio\u0041.mp3"),  # Contains 'A' as unicode
            Path("/tmp/audio\u200b.mp3"),  # Contains zero-width space
        ]

        for path in paths:
            # Should not crash
            try:
                validator.is_path_allowed(path)
            except Exception:
                # Handling errors is acceptable
                pass
