# Virtual Character MCP Server

A Model Context Protocol (MCP) server that provides a unified middleware layer for controlling virtual characters across multiple backend platforms (VRChat, Blender, Unity, etc.).

## Features

- **Plugin-Based Architecture**: Easily extensible with new backend adapters
- **Canonical Data Model**: Universal animation format that all backends can translate
- **Multiple Backends**: Support for VRChat (remote), Blender, Unity, and more
- **Video Capture**: Get visual feedback from the agent's perspective
- **Bidirectional Communication**: Receive state updates from virtual environments
- **High-Level Behaviors**: Execute complex behaviors with simple commands

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

2. Configure the server:
```bash
cp config/server_config.json.example config/server_config.json
# Edit config/server_config.json with your settings
```

3. For VRChat remote setup:
   - Set up Windows bridge server on GPU machine
   - Configure OBS Studio with WebSocket plugin
   - Set environment variables for remote host

## Usage

### Starting the Server

```bash
# Using the startup script
./scripts/start_server.sh

# Or directly with Python
python -m tools.mcp.virtual_character.server

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

| Tool | Description |
|------|-------------|
| `set_backend` | Switch to a different backend system |
| `send_animation` | Send animation data (emotion, gesture, blend shapes) |
| `send_audio` | Send audio data with optional text |
| `capture_view` | Capture current view from agent perspective |
| `receive_state` | Get current state from virtual environment |
| `execute_behavior` | Execute high-level behavior (greet, dance, sit, etc.) |
| `change_environment` | Change virtual environment/background |
| `list_backends` | List available backend plugins |
| `get_backend_status` | Get status of current backend |

### Example Usage

```python
import aiohttp
import asyncio

async def control_character():
    async with aiohttp.ClientSession() as session:
        # Set backend to mock for testing
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
virtual_character/
├── backends/           # Backend adapter implementations
│   ├── base.py        # Base adapter interface
│   ├── mock.py        # Mock backend for testing
│   └── vrchat_remote.py  # VRChat remote backend
├── models/            # Data models
│   └── canonical.py   # Universal data formats
├── server/            # Server implementation
│   ├── server.py      # Main MCP server
│   └── plugin_manager.py  # Plugin discovery and management
├── config/            # Configuration files
├── scripts/           # Utility scripts
└── tests/             # Unit tests
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
