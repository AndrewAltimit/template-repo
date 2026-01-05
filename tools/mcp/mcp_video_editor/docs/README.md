# Video Editor MCP Server

> A Model Context Protocol server for intelligent automated video editing, providing transcript analysis, speaker diarization, scene detection, and dynamic video composition.

## Overview

The Video Editor MCP Server processes multi-feed video content and creates professionally edited outputs based on speaker activity, content importance, and configurable rules. It combines state-of-the-art AI models for transcription (Whisper) and speaker diarization (pyannote/diart) with powerful video editing capabilities (MoviePy).

## Features

### Core Capabilities

- **Automatic Transcription**: Generate accurate transcripts with word-level timestamps using OpenAI Whisper
- **Speaker Diarization**: Identify and track different speakers throughout the video
- **Scene Detection**: Automatically detect scene changes for intelligent cut points
- **Smart Editing**: Create edit decision lists (EDL) based on configurable rules
- **Multi-feed Support**: Handle 2-16 simultaneous video inputs
- **Effects Library**: Transitions, zooms, picture-in-picture, lower thirds
- **Caption Generation**: Add styled captions in multiple languages
- **Clip Extraction**: Extract highlights based on keywords, speakers, or timestamps

### Processing Modes

- **Real-time Mode**: Stream processing for live events with low-latency switching
- **Batch Mode**: Queue multiple videos with template-based editing rules
- **Preview Mode**: Low-quality quick renders for rapid iteration

## Installation

### Prerequisites

```bash
# System dependencies
sudo apt-get update
sudo apt-get install -y ffmpeg

# Python dependencies (will be installed automatically in Docker)
pip install openai-whisper
pip install moviepy
pip install pyannote.audio
pip install librosa
pip install opencv-python
```

### Docker Installation (Recommended)

The Video Editor MCP Server runs in a Docker container for consistency:

```bash
# Build the container
docker-compose build mcp-video-editor

# Start the server
docker-compose up -d mcp-video-editor
```

### Local Installation

```bash
# Install Python dependencies
pip install -r tools/mcp/video_editor/requirements.txt

# Start the server
python -m mcp_video_editor.server
```

## Configuration

### Environment Variables

```bash
# Model configuration
WHISPER_MODEL=medium          # Whisper model size (tiny, base, small, medium, large)
WHISPER_DEVICE=cuda           # Device for Whisper (cuda or cpu)
DIART_DEVICE=cuda             # Device for speaker diarization

# CRITICAL: Required for full speaker diarization functionality
# Speaker identification features require a Hugging Face token with access to pyannote models
# Without this token, speaker diarization will be disabled (graceful degradation)
# Get your token at: https://huggingface.co/settings/tokens
# Accept pyannote terms at: https://huggingface.co/pyannote/speaker-diarization
HUGGINGFACE_TOKEN=your_token  # Required for speaker diarization (pyannote.audio models)

# Processing defaults
TRANSITION_DURATION=0.5        # Default transition duration in seconds
SPEAKER_SWITCH_DELAY=0.8      # Minimum time between speaker switches
SILENCE_THRESHOLD=2.0          # Minimum silence duration to remove
ZOOM_FACTOR=1.3               # Zoom factor for emphasis
PIP_SIZE=0.25                 # Picture-in-picture size ratio

# Performance settings
MAX_PARALLEL_JOBS=2           # Maximum concurrent rendering jobs
VIDEO_CACHE_SIZE=2GB          # Maximum video cache size
ENABLE_GPU=true               # Enable GPU acceleration
CHUNK_SIZE=300                # Seconds per processing chunk

# Directory configuration
MCP_VIDEO_OUTPUT_DIR=/app/output
MCP_VIDEO_CACHE_DIR=~/.cache/mcp_video_editor
MCP_VIDEO_TEMP_DIR=/tmp/video_editor
```

## MCP Tool Methods

### video_editor/analyze

Analyzes video content without rendering, returns metadata and suggested edits.

```python
# Example request
{
    "tool": "video_editor/analyze",
    "arguments": {
        "video_inputs": ["meeting_cam1.mp4", "meeting_cam2.mp4"],
        "analysis_options": {
            "transcribe": true,
            "identify_speakers": true,
            "detect_scenes": true,
            "extract_highlights": true
        }
    }
}

# Response includes:
# - Full transcript with timestamps
# - Speaker identification and segments
# - Audio analysis (volume, silence, peaks)
# - Scene change detection
# - Highlight extraction
# - Suggested edit points
```

### video_editor/create_edit

Generates an edit decision list (EDL) based on rules without rendering.

```python
# Example request
{
    "tool": "video_editor/create_edit",
    "arguments": {
        "video_inputs": ["presenter.mp4", "audience.mp4"],
        "editing_rules": {
            "switch_on_speaker": true,
            "speaker_switch_delay": 0.5,
            "picture_in_picture": "auto",
            "zoom_on_emphasis": true,
            "remove_silence": true,
            "silence_threshold": 2.0
        },
        "speaker_mapping": {
            "SPEAKER_00": "presenter.mp4",
            "SPEAKER_01": "audience.mp4"
        }
    }
}

# Note: Speaker Mapping Behavior
# - If speaker_mapping is provided, speakers are explicitly mapped to videos
# - If omitted with multiple videos, speakers are auto-mapped using deterministic MD5 hash
# - Auto-mapping ensures consistent results across runs but may not match expectations
# - For predictable results, always provide explicit speaker_mapping

# Returns edit decision list with:
# - Timestamp and duration for each segment
# - Source video selection
# - Transitions and effects
# - Estimated final duration
```

### video_editor/render

Executes the actual video rendering based on EDL or automatic rules.

```python
# Example request
{
    "tool": "video_editor/render",
    "arguments": {
        "video_inputs": ["input1.mp4", "input2.mp4"],
        "edit_decision_list": [...],  # Optional, auto-generated if not provided
        "output_settings": {
            "format": "mp4",
            "resolution": "1920x1080",
            "fps": 30,
            "bitrate": "8M",
            "output_path": "output/final_edit.mp4"
        },
        "render_options": {
            "hardware_acceleration": true,
            "preview_mode": false,
            "add_captions": true,
            "add_speaker_labels": true
        }
    }
}

# Returns:
# - Output file path
# - Duration and file size
# - Render time statistics
# - Optional transcript file path
```

### video_editor/extract_clips

Creates short clips based on transcript keywords or timestamps.

```python
# Example request
{
    "tool": "video_editor/extract_clips",
    "arguments": {
        "video_input": "presentation.mp4",
        "extraction_criteria": {
            "keywords": ["important", "key point", "summary"],
            "speakers": ["SPEAKER_00"],
            "time_ranges": [[60.0, 90.0], [180.0, 210.0]],
            "min_clip_length": 3.0,
            "max_clip_length": 60.0,
            "padding": 0.5
        }
    }
}

# Returns list of extracted clips with:
# - Output paths
# - Timestamps
# - Extraction criteria met
```

### video_editor/add_captions

Adds styled captions to existing video using transcript.

```python
# Example request
{
    "tool": "video_editor/add_captions",
    "arguments": {
        "video_input": "video.mp4",
        "caption_style": {
            "font": "Arial",
            "size": 42,
            "color": "#FFFFFF",
            "background": "#000000",
            "position": "bottom",
            "max_chars_per_line": 40,
            "display_speaker_names": true
        },
        "languages": ["en", "es", "fr"]
    }
}

# Returns:
# - Output video paths (one per language)
# - SRT subtitle files
# - Caption statistics
```

## Smart Editing Rules

### Speaker-Based Switching
- Automatic camera switching to active speaker
- Configurable delay to avoid rapid switching
- Picture-in-picture for conversations
- Split-screen for debates/panels

### Content-Based Editing
- Zoom on emphasis (volume/pitch analysis)
- Highlight detection from transcript keywords
- Automatic b-roll insertion points
- Scene change detection

### Audio-Driven Effects
- Auto-remove long silences
- Background music ducking
- Laughter/applause detection
- Cross-talk handling

## Usage Examples

### Basic Two-Camera Interview

```python
import asyncio
from tools.mcp.core.client import MCPClient

async def edit_interview():
    async with MCPClient("video_editor", port=8019) as client:
        # Analyze both camera feeds
        analysis = await client.call("video_editor/analyze", {
            "video_inputs": ["interviewer.mp4", "interviewee.mp4"]
        })

        # Create edit with speaker switching
        edit = await client.call("video_editor/create_edit", {
            "video_inputs": ["interviewer.mp4", "interviewee.mp4"],
            "editing_rules": {
                "switch_on_speaker": True,
                "remove_silence": True
            }
        })

        # Render final video
        result = await client.call("video_editor/render", {
            "video_inputs": ["interviewer.mp4", "interviewee.mp4"],
            "edit_decision_list": edit["edit_decision_list"],
            "render_options": {
                "add_captions": True
            }
        })

        print(f"Edited video: {result['output_path']}")

asyncio.run(edit_interview())
```

### Extract Highlight Reel

```python
async def create_highlights():
    async with MCPClient("video_editor", port=8019) as client:
        # Extract clips with important moments
        clips = await client.call("video_editor/extract_clips", {
            "video_input": "conference_talk.mp4",
            "extraction_criteria": {
                "keywords": ["breakthrough", "innovation", "results"],
                "min_clip_length": 5.0,
                "max_clip_length": 30.0
            }
        })

        print(f"Extracted {clips['total_clips']} highlight clips")
```

### Multi-Language Captioning

```python
async def add_multilingual_captions():
    async with MCPClient("video_editor", port=8019) as client:
        result = await client.call("video_editor/add_captions", {
            "video_input": "presentation.mp4",
            "languages": ["en", "es", "fr", "de"],
            "caption_style": {
                "size": 48,
                "position": "bottom",
                "display_speaker_names": True
            }
        })

        for lang_result in result["languages_processed"]:
            print(f"{lang_result['language']}: {lang_result['output_path']}")
```

## Performance Optimization

### GPU Acceleration
- CUDA support for Whisper transcription
- Hardware-accelerated video encoding (NVENC, QSV)
- GPU-based scene detection with OpenCV

### Memory Management
- Chunked processing for long videos
- Smart video caching with configurable limits
- Automatic cache cleanup

### Parallel Processing
- Concurrent transcription and analysis
- Multi-threaded video rendering
- Job queue management

## Architecture

### Components

1. **MCP Server** (`server.py`)
   - Handles MCP protocol communication
   - Job management and progress tracking
   - Configuration and resource management

2. **Audio Processor** (`processors/audio_processor.py`)
   - Whisper transcription integration
   - Speaker diarization with pyannote
   - Audio level analysis
   - Silence detection

3. **Video Processor** (`processors/video_processor.py`)
   - MoviePy video editing
   - Effects and transitions
   - Caption rendering
   - Scene detection

4. **Tools** (`tools.py`)
   - MCP tool implementations
   - Edit decision list generation
   - Rendering orchestration

## Error Handling

The server provides detailed error codes:

- `VIDEO_NOT_FOUND`: Input video file does not exist
- `INVALID_FORMAT`: Unsupported video format
- `INSUFFICIENT_MEMORY`: Not enough memory for processing
- `SPEAKER_DETECTION_FAILED`: Could not identify distinct speakers
- `TRANSCRIPTION_FAILED`: Whisper failed to generate transcript
- `RENDER_FAILED`: MoviePy rendering error
- `INVALID_EDL`: Edit decision list validation failed

## Testing

Run the comprehensive test suite:

```bash
# Run all video editor tests
pytest tests/test_video_editor.py -v

# Run with coverage
pytest tests/test_video_editor.py --cov=mcp_video_editor

# Run in Docker
docker-compose run --rm python-ci pytest tests/test_video_editor.py
```

## Troubleshooting

### Common Issues

1. **CUDA out of memory**
   - Reduce `WHISPER_MODEL` size
   - Set `WHISPER_DEVICE=cpu`
   - Decrease `VIDEO_CACHE_SIZE`

2. **Slow transcription**
   - Use smaller Whisper model
   - Enable GPU acceleration
   - Process in smaller chunks

3. **Speaker diarization not working**
   - Ensure `HUGGINGFACE_TOKEN` is set
   - Check pyannote.audio installation
   - Verify audio quality

4. **Video rendering fails**
   - Check ffmpeg installation
   - Verify codec support
   - Ensure sufficient disk space

## Future Enhancements

- **AI Scene Understanding**: Use vision models for visual moment detection
- **Music Synchronization**: Auto-sync cuts to beat detection
- **Template Library**: Pre-built editing styles (podcast, interview, presentation)
- **Cloud Rendering**: Offload heavy processing to cloud GPUs
- **Collaborative Editing**: Multiple users can review and modify EDLs
- **Real-time Streaming**: Live editing with minimal latency

## License

This project is part of the template-repo and follows its licensing terms.

## Support

For issues or questions, please refer to the main repository documentation or create an issue on GitHub.
