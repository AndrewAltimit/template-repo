# Virtual Character MCP Server

> A Model Context Protocol server for controlling virtual characters across multiple platforms (VRChat, Blender, Unity), with comprehensive audio support, lip-sync animation, and event sequencing for synchronized multimedia performances.

## Features

### Core Capabilities
- **Plugin-Based Architecture**: Easily extensible with new backend adapters
- **Canonical Data Model**: Universal animation format that all backends can translate
- **Multiple Backends**: Support for VRChat (remote), Blender, Unity, and more
- **Video Capture**: Get visual feedback from the agent's perspective
- **Bidirectional Communication**: Receive state updates from virtual environments
- **High-Level Behaviors**: Execute complex behaviors with simple commands

### Audio Support
- **Multi-Format Support**: Base64 audio transmission (MP3, WAV, Opus, PCM)
- **ElevenLabs Integration**: Full support for expression tags (`[laughs]`, `[whisper]`, etc.)
- **Lip-Sync Animation**: Viseme data generation for realistic mouth movements
- **Audio Streaming**: Chunk-based transmission for large audio files
- **Expression Mapping**: Automatic emotion detection from audio tags

### Storage Service (Critical for AI Agents)
- **Context Optimization**: Prevents base64 audio from polluting AI context windows
- **Auto-Upload**: File paths are automatically uploaded to storage when sending to remote servers
- **Cross-Machine Transfer**: Seamless file exchange between VM, containers, and hosts
- **Secure Transfer**: Token-based authentication with HMAC-SHA256
- **Auto-Cleanup**: Files expire after configurable TTL (default 1 hour)
- **Universal Support**: Audio, animations, textures, configurations

**Important**: The storage service is essential for efficient AI agent operation. Without it, audio data will be sent as base64, consuming valuable context tokens.

### Event Sequencing
- **Complex Sequences**: Build performances with synchronized audio and animation
- **Event Types**: Animation, audio, expression, movement, wait, and parallel events
- **Playback Control**: Play, pause, resume, and stop sequences on demand
- **Loop Support**: Create repeating sequences for ambient behaviors
- **Parallel Events**: Execute multiple actions simultaneously
- **Priority Management**: Interrupt handling for important events

## Architecture

The server uses a plugin-based architecture where each backend (VRChat, Blender, Unity, etc.) is implemented as a separate adapter that conforms to the `BackendAdapter` interface.

```
AI Agent → MCP Server → Plugin Manager → Backend Adapter → Virtual Platform
                ↑                              ↓
                └──────── State Updates ←──────┘
```

## Installation

### Requirements

- Python 3.10+
- Required Python packages (see requirements.txt)
- For VRChat: Windows machine with GPU (remote setup supported)
- For Blender: Blender 3.0+
- For Unity: Unity with WebSocket support

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables (**CRITICAL STEP**):
```bash
# Copy example environment file
cp .env.example .env

# Generate a secure storage key (REQUIRED for efficient operation)
python -c "import secrets; print(secrets.token_hex(32))"

# Add to .env file:
# STORAGE_SECRET_KEY=<your_generated_key>
# STORAGE_BASE_URL=http://192.168.0.152:8021  # Or your storage server URL
```

**Important**: Both local and remote machines must have the same `STORAGE_SECRET_KEY` in their .env files for authentication to work.

3. Start the storage service (recommended):
```bash
# Using Docker (preferred)
docker-compose up virtual-character-storage

# Or run directly
python tools/mcp/mcp_virtual_character/storage_service/server.py
```

4. For VRChat remote setup:
   - Set up Windows bridge server on GPU machine
   - Configure OBS Studio with WebSocket plugin
   - Set environment variables for remote host
   - Use Windows launchers in `automation/launchers/windows/virtual-character/`

## Usage

### Starting the Server

```bash
# Using the startup script
./scripts/start_server.sh

# Or directly with Python
python -m mcp_virtual_character.server

# With custom port
export VIRTUAL_CHARACTER_PORT=8025
./scripts/start_server.sh
```

### Testing the Server

```bash
# Run the test script
python scripts/test_server.py
```

### Available MCP Tools

#### Core Animation & Control
| Tool | Description |
|------|-------------|
| `set_backend` | Switch to a different backend system |
| `send_animation` | Send animation data (emotion, gesture, movement parameters) |
| `execute_behavior` | Execute high-level behavior (greet, dance, sit, etc.) |
| `reset` | Reset all states - clear emotes and stop all movement |
| `list_backends` | List available backend plugins |
| `get_backend_status` | Get status of current backend |

#### Audio & Speech (NEW)
| Tool | Description |
|------|-------------|
| `send_audio` | Send audio with optional lip-sync metadata and expression tags |

#### Event Sequencing (NEW)
| Tool | Description |
|------|-------------|
| `create_sequence` | Create a new event sequence for coordinated performances |
| `add_sequence_event` | Add events to the current sequence |
| `play_sequence` | Play the current or specified sequence |
| `pause_sequence` | Pause the currently playing sequence |
| `resume_sequence` | Resume a paused sequence |
| `stop_sequence` | Stop the currently playing sequence |
| `get_sequence_status` | Get status of current sequence playback |

### AI Agent Usage Guidelines

When using this server with Claude, GPT, or other AI agents via MCP, follow these guidelines to avoid context pollution.

#### Recommended: Use File Paths
```python
# Good - File path will be auto-uploaded to storage
mcp__virtual-character__play_audio(
    audio_data="outputs/elevenlabs_speech/2025-09-17/speech.mp3"
)
```

#### Recommended: Use Storage URLs
```python
# Good - Direct storage URL, no upload needed
mcp__virtual-character__play_audio(
    audio_data="http://192.168.0.152:8021/download/abc123"
)
```

#### Avoid: Base64 Data
```python
# Bad - Pollutes context window with large base64 string
import base64
with open('audio.mp3', 'rb') as f:
    audio_base64 = base64.b64encode(f.read()).decode()
mcp__virtual-character__play_audio(audio_data=audio_base64)  # AVOID!
```

The server automatically detects file paths and uploads them to the storage service, keeping your AI context clean and efficient.

### Example Usage

#### Basic Animation Control
```python
import aiohttp
import asyncio

async def control_character():
    async with aiohttp.ClientSession() as session:
        # Set backend to VRChat
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "set_backend",
                "params": {
                    "backend": "vrchat_remote",
                    "config": {"remote_host": "192.168.1.100"}
                }
            }
        )

        # Send animation with emotion
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "send_animation",
                "params": {
                    "emotion": "happy",
                    "gesture": "wave",
                    "emotion_intensity": 0.8
                }
            }
        )
```

#### Audio with ElevenLabs Integration
```python
# Generate speech with ElevenLabs
from tools.mcp.elevenlabs_speech.client import ElevenLabsClient

async def speak_with_emotion():
    # Generate audio with expression tags
    elevenlabs = ElevenLabsClient()
    audio_data = await elevenlabs.synthesize(
        "Hello! [laughs] It's wonderful to meet you [whisper] finally.",
        voice="Sarah"
    )

    # Send to virtual character with expression tags
    await session.post(
        "http://localhost:8020/mcp/execute",
        json={
            "tool": "send_audio",
            "params": {
                "audio_data": audio_data["base64"],
                "expression_tags": ["laughs", "whisper"],
                "text": audio_data["text"]
            }
        }
    )

#### Seamless Audio Flow (Recommended)
```python
# Automatically handles storage upload for optimal performance
from mcp_virtual_character.seamless_audio import play_audio_seamlessly

async def efficient_tts_playback():
    # Generate audio with ElevenLabs
    audio_path = await elevenlabs.synthesize_to_file(
        "Hello world! This is a test of seamless audio.",
        output_path="/tmp/speech.mp3"
    )

    # Play on virtual character
    # Automatically:
    # - Detects local file
    # - Uploads to storage service
    # - Sends only URL to remote server
    # - Keeps context window clean
    result = await play_audio_seamlessly(
        audio_path,
        character_server="http://192.168.0.152:8020",
        text="Hello world! This is a test of seamless audio."
    )

    print(f"Playback {'successful' if result['success'] else 'failed'}")

# Even simpler with MCP integration
async def mcp_seamless_audio():
    # The MCP tool automatically uses storage when available
    await mcp_client.call_tool(
        "play_audio",
        audio_data="/tmp/elevenlabs_audio/speech.mp3",  # Just pass the path!
        text="The text for lip-sync"
    )
    # The server detects it's a local file and handles storage upload
```

#### Creating Complex Sequences
```python
# Build a complete performance sequence
async def create_performance():
    # Create sequence
    await session.post(
        "http://localhost:8020/mcp/execute",
        json={
            "tool": "create_sequence",
            "params": {"name": "greeting_performance"}
        }
    )

    # Add synchronized events
    events = [
        {"event_type": "expression", "expression": "happy", "timestamp": 0},
        {"event_type": "animation", "gesture": "wave", "timestamp": 0.5},
        {"event_type": "audio", "audio_data": audio_base64, "timestamp": 1.0},
        {"event_type": "movement", "move_forward": 0.5, "timestamp": 3.0}
    ]

    for event in events:
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "set_backend",
                "parameters": {
                    "backend": "mock",
                    "config": {"world_name": "TestWorld"}
                }
            }
        )

        # Send animation
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "send_animation",
                "parameters": {
                    "emotion": "happy",
                    "gesture": "wave"
                }
            }
        )

        # Capture view
        resp = await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "capture_view",
                "parameters": {"format": "jpeg"}
            }
        )
        result = await resp.json()
        # Process captured frame...

asyncio.run(control_character())
```

## Documentation

- [Remote Setup Guide](docs/REMOTE_SETUP.md) - Running on Windows with VRChat
- [VRChat Backend Details](docs/VRCHAT_BACKEND.md) - OSC protocol and avatar control
- [Audio Sequencing Guide](docs/AUDIO_SEQUENCING.md) - Creating synchronized performances
- [VRChat Audio Setup](docs/VRCHAT_AUDIO_SETUP.md) - Audio routing requirements for VRChat
- [VoiceMeeter Setup Guide](docs/VOICEMEETER_SETUP.md) - Comprehensive VoiceMeeter configuration for AI voice

## Backend Adapters

### Mock Backend (Built-in)

A testing backend that simulates a virtual character system without external dependencies.

**Features:**
- Simulated video frames
- Environment state tracking
- Event generation
- Animation history

**Configuration:**
```json
{
  "world_name": "TestWorld",
  "simulate_events": true
}
```

### VRChat Remote Backend

Controls VRChat avatars on a remote Windows machine with GPU.

**Requirements:**
- Windows machine with NVIDIA GPU
- VRChat installed via Steam
- OBS Studio with WebSocket plugin
- Bridge server running on Windows

**Configuration:**
```json
{
  "remote_host": "192.168.0.150",
  "bridge_port": 8021,
  "stream_port": 8022,
  "obs_port": 4455,
  "obs_password": "your_password",
  "avatar_config": "./config/avatars/default.yaml"
}
```

### Creating Custom Backends

To create a new backend adapter:

1. Create a new file in `backends/` directory
2. Inherit from `BackendAdapter` base class
3. Implement all required methods
4. Register via entry points or place in backends directory

Example:
```python
from backends.base import BackendAdapter

class CustomBackend(BackendAdapter):
    @property
    def backend_name(self) -> str:
        return "custom"

    async def connect(self, config):
        # Connect to your platform
        return True

    async def send_animation_data(self, data):
        # Translate and send animation
        return True

    # ... implement other required methods
```

## Data Models

### Canonical Animation Data

The universal format used by all backends:

- **Emotions**: neutral, happy, sad, angry, surprised, fearful, disgusted
- **Gestures**: wave, point, thumbs_up, nod, shake_head, dance, etc.
- **Visemes**: Full set for accurate lip-sync (AA, EE, IH, OH, UH, etc.)
- **Blend Shapes**: Facial animation weights (0-1)
- **Bone Transforms**: Skeletal animation data
- **Locomotion**: Movement state and velocity

### Environment State

Information about the virtual world:

- World name and instance ID
- Agent position and rotation
- Nearby agents and objects
- Interaction zones
- Environmental conditions

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_models.py -v
pytest tests/test_backend.py -v
pytest tests/test_plugin_manager.py -v
```

## Development

### Project Structure

```
mcp_virtual_character/
├── mcp_virtual_character/  # Main package
│   ├── backends/           # Backend adapter implementations
│   │   ├── base.py         # Base adapter interface
│   │   ├── mock.py         # Mock backend for testing
│   │   └── vrchat_remote.py  # VRChat remote backend
│   ├── models/             # Data models
│   │   └── canonical.py    # Universal data formats
│   ├── server.py           # Main MCP server
│   ├── audio_handler.py    # Audio processing and playback
│   └── sequence_handler.py # Event sequence management
├── storage_service/        # Audio/file storage service
│   └── server.py           # Storage API server
├── scripts/                # Utility scripts
├── tests/                  # Unit tests
└── README.md
```

### Contributing

1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Follow the canonical data model

## Troubleshooting

### Server won't start
- Check port availability: `lsof -i :8020`
- Verify Python version: `python --version` (requires 3.10+)
- Check logs for errors

### VRChat connection fails
- Ensure Windows bridge server is running
- Check firewall settings
- Verify OBS WebSocket is enabled
- Test network connectivity to remote host

### No video capture
- Verify backend supports video capture
- Check OBS Virtual Camera is running (for VRChat)
- Ensure proper permissions for screen capture

## License

See LICENSE file in repository root.

## Support

For issues or questions, please open an issue on the GitHub repository.
