"""Comprehensive tests for the Video Editor MCP Server"""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Import the video editor components
from tools.mcp.video_editor import VideoEditorMCPServer
from tools.mcp.video_editor.processors import AudioProcessor, VideoProcessor
from tools.mcp.video_editor.tools import add_captions, analyze_video, create_edit, extract_clips, render_video


class TestVideoEditorMCPServer(unittest.TestCase):
    """Test the main Video Editor MCP Server"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.server = VideoEditorMCPServer(output_dir=self.temp_dir)

    def tearDown(self):
        """Clean up after tests"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_server_initialization(self):
        """Test server initializes correctly"""
        self.assertEqual(self.server.port, 8019)
        self.assertEqual(self.server.name, "Video Editor MCP Server")
        self.assertTrue(os.path.exists(self.server.output_dir))
        self.assertTrue(os.path.exists(self.server.cache_dir))

    def test_config_loading(self):
        """Test configuration is loaded properly"""
        config = self.server._load_config()
        self.assertIn("models", config)
        self.assertIn("defaults", config)
        self.assertIn("performance", config)
        self.assertIn("whisper_model", config["models"])

    def test_job_management(self):
        """Test job creation and management"""
        job_id = self.server.create_job("test_operation")
        self.assertIn("job_", job_id)
        self.assertIn(job_id, self.server.active_jobs)

        # Test job update
        self.server.update_job(job_id, {"progress": 50, "stage": "processing"})
        job = self.server.get_job_status(job_id)
        self.assertEqual(job["progress"], 50)
        self.assertEqual(job["stage"], "processing")

        # Test job cleanup
        self.server.cleanup_job(job_id)

    def test_cuda_detection(self):
        """Test CUDA availability detection"""
        with patch("torch.cuda.is_available") as mock_cuda:
            mock_cuda.return_value = True
            self.assertTrue(self.server._check_cuda())

            mock_cuda.return_value = False
            self.assertFalse(self.server._check_cuda())

    async def test_handle_tool_call(self):
        """Test handling tool calls"""
        # Test with valid tool
        with patch("tools.mcp.video_editor.tools.TOOLS", {"test_tool": MagicMock(return_value={"result": "success"})}):
            result = await self.server.handle_tool_call("test_tool", {})
            self.assertEqual(result["result"], "success")

        # Test with invalid tool
        result = await self.server.handle_tool_call("invalid_tool", {})
        self.assertIn("error", result)


class TestAudioProcessor(unittest.TestCase):
    """Test the Audio Processor module"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "models": {"whisper_model": "base", "whisper_device": "cpu", "diart_device": "cpu"},
            "defaults": {"silence_threshold": 2.0},
        }
        self.logger = MagicMock()
        self.processor = AudioProcessor(self.config, self.temp_dir, self.logger)

    def tearDown(self):
        """Clean up after tests"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("subprocess.run")
    def test_extract_audio(self, mock_run):
        """Test audio extraction from video"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_file:
            video_path = video_file.name

            try:
                audio_path = self.processor.extract_audio(video_path)
                self.assertTrue(audio_path.endswith(".wav"))

                # Verify ffmpeg was called correctly
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                self.assertEqual(call_args[0], "ffmpeg")
                self.assertIn("-i", call_args)
                self.assertIn(video_path, call_args)

            finally:
                os.unlink(video_path)
                if os.path.exists(audio_path):
                    os.unlink(audio_path)

    @patch("tools.mcp.video_editor.processors.audio_processor.whisper")
    def test_transcribe(self, mock_whisper):
        """Test audio transcription"""
        # Mock Whisper model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Test transcription",
            "language": "en",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Test",
                    "words": [{"word": "Test", "start": 0.0, "end": 1.0, "probability": 0.95}],
                }
            ],
        }

        with patch.object(self.processor, "_whisper_model", mock_model):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
                audio_path = audio_file.name

                try:
                    result = self.processor.transcribe(audio_path)
                    self.assertEqual(result["text"], "Test transcription")
                    self.assertEqual(result["language"], "en")
                    self.assertEqual(len(result["segments"]), 1)
                    self.assertEqual(len(result["words"]), 1)

                finally:
                    os.unlink(audio_path)

    def test_cache_operations(self):
        """Test caching functionality"""
        # Test cache key generation
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

            try:
                cache_key = self.processor._get_cache_key(temp_path, "test_op", "arg1")
                self.assertIsInstance(cache_key, str)
                self.assertEqual(len(cache_key), 64)  # SHA256 hash length

                # Test cache save and load
                test_data = {"test": "data", "value": 123}
                self.processor._save_to_cache(cache_key, test_data, self.temp_dir)

                loaded_data = self.processor._load_from_cache(cache_key, self.temp_dir)
                self.assertEqual(loaded_data, test_data)

            finally:
                os.unlink(temp_path)

    def test_combine_transcript_with_speakers(self):
        """Test combining transcript with speaker diarization"""
        transcript = {
            "text": "Hello world",
            "language": "en",
            "segments": [{"start": 0.0, "end": 1.0, "text": "Hello"}, {"start": 1.0, "end": 2.0, "text": "world"}],
        }

        diarization = {
            "speakers": [{"id": "SPEAKER_00", "total_speaking_time": 2.0}],
            "segments": [{"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0}],
        }

        result = self.processor.combine_transcript_with_speakers(transcript, diarization)
        self.assertEqual(len(result["segments_with_speakers"]), 2)
        self.assertEqual(result["segments_with_speakers"][0]["speaker"], "SPEAKER_00")


class TestVideoProcessor(unittest.TestCase):
    """Test the Video Processor module"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "defaults": {"transition_duration": 0.5, "zoom_factor": 1.3, "pip_size": 0.25},
            "performance": {"video_cache_size": "100MB", "enable_gpu": False},
        }
        self.logger = MagicMock()
        self.processor = VideoProcessor(self.config, self.temp_dir, self.logger)

    def tearDown(self):
        """Clean up after tests"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cache_size_parsing(self):
        """Test parsing of cache size strings"""
        self.assertEqual(self.processor._parse_cache_size("1GB"), 1024 * 1024 * 1024)
        self.assertEqual(self.processor._parse_cache_size("100MB"), 100 * 1024 * 1024)
        self.assertEqual(self.processor._parse_cache_size("50KB"), 50 * 1024)
        self.assertEqual(self.processor._parse_cache_size("1000"), 1000)

    @patch("tools.mcp.video_editor.processors.video_processor.moviepy")
    def test_load_video(self, mock_moviepy):
        """Test video loading and caching"""
        mock_clip = MagicMock()
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.duration = 10
        mock_moviepy.VideoFileClip.return_value = mock_clip

        with patch.object(self.processor, "_moviepy", mock_moviepy):
            # First load - should load from file
            clip1 = self.processor.load_video("test.mp4")
            self.assertEqual(clip1, mock_clip)
            self.assertIn("test.mp4", self.processor._video_cache)

            # Second load - should use cache
            clip2 = self.processor.load_video("test.mp4")
            self.assertEqual(clip2, mock_clip)
            # Should only be called once due to caching
            mock_moviepy.VideoFileClip.assert_called_once()

    def test_wrap_text(self):
        """Test text wrapping for captions"""
        text = "This is a very long sentence that needs to be wrapped to multiple lines"
        wrapped = self.processor._wrap_text(text, 20)
        lines = wrapped.split("\n")

        for line in lines:
            self.assertLessEqual(len(line), 20)

        # Verify all words are preserved
        original_words = set(text.split())
        wrapped_words = set(wrapped.replace("\n", " ").split())
        self.assertEqual(original_words, wrapped_words)


@pytest.mark.asyncio
class TestVideoEditorTools:
    """Test the video editor tool functions"""

    @pytest.fixture
    def mock_server(self):
        """Create a mock server for testing"""
        server = MagicMock(spec=VideoEditorMCPServer)
        server.logger = MagicMock()
        server.audio_processor = MagicMock(spec=AudioProcessor)
        server.video_processor = MagicMock(spec=VideoProcessor)
        server.renders_dir = "/tmp/renders"
        server.clips_dir = "/tmp/clips"
        server.edl_dir = "/tmp/edl"
        server.job_counter = 1
        return server

    async def test_analyze_video_missing_inputs(self, mock_server):
        """Test analyze_video with missing inputs"""
        result = await analyze_video(video_inputs=[], _server=mock_server)
        assert "error" in result
        assert "No video inputs" in result["error"]

    async def test_analyze_video_file_not_found(self, mock_server):
        """Test analyze_video with non-existent file"""
        result = await analyze_video(video_inputs=["/nonexistent/video.mp4"], _server=mock_server)
        assert "error" in result
        assert "not found" in result["error"]

    @patch("os.path.exists", return_value=True)
    @patch("os.path.getsize", return_value=1000000)
    async def test_analyze_video_success(self, mock_exists, mock_size, mock_server):
        """Test successful video analysis"""
        # Mock audio processor methods
        mock_server.audio_processor.extract_audio.return_value = "/tmp/audio.wav"
        mock_server.audio_processor.transcribe.return_value = {"text": "Test transcript", "language": "en", "segments": []}
        mock_server.audio_processor.diarize_speakers.return_value = {"speakers": [], "segments": []}
        mock_server.audio_processor.analyze_audio_levels.return_value = {
            "duration": 10.0,
            "silence_segments": [],
            "volume_profile": [],
            "peak_moments": [],
        }

        # Mock video processor methods
        mock_server.video_processor.detect_scene_changes.return_value = [5.0, 10.0]

        with patch("os.unlink"):
            result = await analyze_video(video_inputs=["test.mp4"], _server=mock_server)

        assert "error" not in result
        assert "analysis" in result
        assert "test.mp4" in result["analysis"]

    @patch("os.path.exists", return_value=True)
    async def test_create_edit_with_speaker_mapping(self, mock_exists, mock_server):
        """Test creating edit with speaker mapping"""
        # Mock analyze_video
        with patch("tools.mcp.video_editor.tools.analyze_video", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "analysis": {
                    "video1.mp4": {
                        "segments_with_speakers": [
                            {"start": 0, "end": 5, "speaker": "SPEAKER_00", "text": "Hello"},
                            {"start": 5, "end": 10, "speaker": "SPEAKER_01", "text": "World"},
                        ],
                        "audio_analysis": {"duration": 10.0, "silence_segments": []},
                        "highlights": [],
                    }
                }
            }

            with patch("builtins.open", create=True), patch("json.dump"):
                result = await create_edit(
                    video_inputs=["video1.mp4", "video2.mp4"],
                    speaker_mapping={"SPEAKER_00": "video1.mp4", "SPEAKER_01": "video2.mp4"},
                    _server=mock_server,
                )

            assert "error" not in result
            assert "edit_decision_list" in result
            assert len(result["edit_decision_list"]) > 0

    async def test_extract_clips_with_keywords(self, mock_server):
        """Test extracting clips based on keywords"""
        with patch("os.path.exists", return_value=True):
            with patch("tools.mcp.video_editor.tools.analyze_video", new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = {
                    "analysis": {
                        "video.mp4": {
                            "transcript": {
                                "segments": [
                                    {"start": 0, "end": 5, "text": "This is important"},
                                    {"start": 10, "end": 15, "text": "Regular content"},
                                ]
                            }
                        }
                    }
                }

                mock_server.video_processor.extract_clip = MagicMock()

                result = await extract_clips(
                    video_input="video.mp4",
                    extraction_criteria={"keywords": ["important"], "min_clip_length": 3.0, "padding": 0.5},
                    _server=mock_server,
                )

                assert "error" not in result
                assert "clips_extracted" in result
                assert len(result["clips_extracted"]) > 0
                mock_server.video_processor.extract_clip.assert_called()


class TestIntegration(unittest.TestCase):
    """Integration tests for the video editor"""

    @patch("tools.mcp.video_editor.server.VideoEditorMCPServer")
    async def test_full_workflow(self, MockServer):
        """Test a complete video editing workflow"""
        # Create a mock server instance
        mock_server = MagicMock(spec=VideoEditorMCPServer)
        mock_server.logger = MagicMock()
        mock_server.renders_dir = "/tmp/renders"
        mock_server.clips_dir = "/tmp/clips"
        mock_server.edl_dir = "/tmp/edl"

        # Mock audio processor
        mock_audio = MagicMock(spec=AudioProcessor)
        mock_audio.extract_audio.return_value = "/tmp/audio.wav"
        mock_audio.transcribe.return_value = {
            "text": "Speaker one talks. Then speaker two responds.",
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 3.0, "text": "Speaker one talks."},
                {"start": 3.0, "end": 7.0, "text": "Then speaker two responds."},
            ],
        }
        mock_audio.diarize_speakers.return_value = {
            "speakers": [{"id": "SPEAKER_00", "total_speaking_time": 3.0}, {"id": "SPEAKER_01", "total_speaking_time": 4.0}],
            "segments": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 3.0},
                {"speaker": "SPEAKER_01", "start": 3.0, "end": 7.0},
            ],
        }
        mock_audio.analyze_audio_levels.return_value = {
            "duration": 7.0,
            "silence_segments": [],
            "volume_profile": [0.5] * 7,
            "peak_moments": [1.5, 5.0],
        }
        mock_server.audio_processor = mock_audio

        # Mock video processor
        mock_video = MagicMock(spec=VideoProcessor)
        mock_video.detect_scene_changes.return_value = [3.0]
        mock_video.create_edit_from_edl.return_value = MagicMock()
        mock_video.render_video.return_value = "/tmp/renders/final_output.mp4"
        mock_video.extract_clip.return_value = "/tmp/clips/clip_001.mp4"
        mock_server.video_processor = mock_video

        # Test the full workflow with patches
        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=1000000):
                with patch("builtins.open", create=True):
                    with patch("json.dump"):
                        # Step 1: Analyze videos
                        analysis_result = await analyze_video(video_inputs=["video1.mp4", "video2.mp4"], _server=mock_server)
                        assert "error" not in analysis_result
                        assert "analysis" in analysis_result

                        # Step 2: Create edit with speaker mapping
                        edit_result = await create_edit(
                            video_inputs=["video1.mp4", "video2.mp4"],
                            speaker_mapping={"SPEAKER_00": "video1.mp4", "SPEAKER_01": "video2.mp4"},
                            _server=mock_server,
                        )
                        assert "error" not in edit_result
                        assert "edit_decision_list" in edit_result

                        # Step 3: Render the final video
                        render_result = await render_video(
                            edl_file="/tmp/edl/edit.json",
                            output_settings={"resolution": "1920x1080", "fps": 30, "format": "mp4"},
                            _server=mock_server,
                        )
                        assert "error" not in render_result
                        assert "output_file" in render_result

                        # Step 4: Extract clips based on keywords
                        extract_result = await extract_clips(
                            video_input="video1.mp4",
                            extraction_criteria={"keywords": ["speaker", "talks"], "min_clip_length": 2.0},
                            _server=mock_server,
                        )
                        assert "error" not in extract_result
                        assert "clips_extracted" in extract_result

                        # Step 5: Add captions to video
                        caption_result = await add_captions(
                            video_input="video1.mp4",
                            transcript={"segments": [{"start": 0, "end": 3, "text": "Test caption"}]},
                            _server=mock_server,
                        )
                        assert "error" not in caption_result
                        assert "output_file" in caption_result

                        # Verify all components were called appropriately
                        mock_audio.extract_audio.assert_called()
                        mock_audio.transcribe.assert_called()
                        mock_video.render_video.assert_called()
                        mock_video.extract_clip.assert_called()


if __name__ == "__main__":
    unittest.main()
