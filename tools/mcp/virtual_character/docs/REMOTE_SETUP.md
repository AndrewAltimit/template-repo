# Virtual Character MCP Server - Remote Setup Guide

This guide explains how to run the Virtual Character MCP Server on a remote Windows machine with VRChat installed, allowing you to control VRChat avatars from anywhere on your network.

## Architecture

```
[Your Machine]                    [Windows Machine with VRChat]
     |                                        |
     | HTTP Requests                          |
     | (Port 8020)                           |
     |-------------------------------------> MCP Server
                                              |
                                              | OSC Protocol
                                              | (Ports 9000/9001)
                                              |
                                              v
                                           VRChat
```

## Prerequisites

### On the Windows Machine (with VRChat)

1. **Python 3.8+** installed
2. **VRChat** installed and configured with OSC enabled
3. **Git** to clone the repository (or copy files manually)
4. **Network access** - ensure firewall allows:
   - Port 8020 (MCP Server)
   - Ports 9000-9001 (VRChat OSC)

### On Your Development Machine

1. Python with `aiohttp` installed (`pip install aiohttp`)

## Setup Instructions

### Step 1: Enable OSC in VRChat

1. Launch VRChat
2. Open the Action Menu (default: R on desktop)
3. Navigate to Options → OSC → Enable
4. Restart VRChat if prompted

### Step 2: Clone/Copy the Repository to Windows Machine

```bash
# On Windows machine
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo
git checkout vrc
```

Or manually copy the `tools/mcp/virtual_character` directory to the Windows machine.

### Step 3: Install Dependencies on Windows

```powershell
# In PowerShell or Command Prompt
pip install python-osc fastapi uvicorn aiohttp
```

### Step 4: Start the MCP Server on Windows

#### Option A: Using PowerShell Script (Recommended)

```powershell
# Navigate to the launchers directory
cd template-repo\automation\launchers\windows\vrchat

# Run the PowerShell script
.\start_server_windows.ps1 -Port 8020 -Host 0.0.0.0
```

#### Option B: Using Batch Script

```cmd
# Navigate to the launchers directory
cd template-repo\automation\launchers\windows\vrchat

# Run the batch file
start_server_windows.bat 8020 0.0.0.0
```

#### Option C: Direct Python Command

```bash
# From repository root
python -m tools.mcp.virtual_character.server --port 8020 --host 0.0.0.0 --mode http
```

**Note:** Convenience scripts are also available in `tools\mcp\virtual_character\scripts\` that redirect to the main launchers.

The server should start and display:
```
Starting Virtual Character MCP Server...
Server will be available at http://0.0.0.0:8020
```

### Step 5: Test from Your Development Machine

```bash
# Test the connection (replace with your Windows machine's IP)
python tools/mcp/virtual_character/scripts/test_remote_server.py \
  --server http://192.168.0.152:8020 \
  --test status

# Run emotion test
python tools/mcp/virtual_character/scripts/test_remote_server.py \
  --server http://192.168.0.152:8020 \
  --test emotions

# Run full test suite
python tools/mcp/virtual_character/scripts/test_remote_server.py \
  --server http://192.168.0.152:8020 \
  --test all
```

## API Endpoints

The MCP server exposes the following HTTP endpoints:

### POST /set_backend
Connect to a backend (vrchat_remote, mock)
```json
{
  "backend": "vrchat_remote",
  "config": {
    "remote_host": "127.0.0.1",
    "use_vrcemote": true,
    "osc_in_port": 9000,
    "osc_out_port": 9001
  }
}
```

### POST /send_animation
Send emotion, gesture, or movement
```json
{
  "emotion": "happy",
  "emotion_intensity": 1.0,
  "gesture": "wave",
  "gesture_intensity": 1.0,
  "parameters": {
    "move_forward": 0.5,
    "look_horizontal": 0.3
  }
}
```

### POST /execute_behavior
Execute high-level behaviors
```json
{
  "behavior": "greet",
  "parameters": {}
}
```

### GET /receive_state
Get current avatar/world state

### GET /list_backends
List available backends

### GET /get_backend_status
Get current backend status and statistics

## Gesture Wheel Mapping

This avatar uses a gesture wheel system. VRCEmote values map to:

- 0 = Neutral/Clear
- 1 = Back (top position)
- 2 = Wave (upper right)
- 3 = Clap (right)
- 4 = Point (lower right)
- 5 = Cheer (lower slightly right)
- 6 = Dance (bottom)
- 7 = Backflip (lower left)
- 8 = Sadness (left)
- 9 = Die (upper left)

Emotions are mapped to appropriate gestures:
- Happy → Cheer (5)
- Sad → Sadness (8)
- Angry → Point (4)
- Surprised → Backflip (7)

## Troubleshooting

### Server Won't Start

1. Check Python is installed: `python --version`
2. Check dependencies: `pip list | grep python-osc`
3. Check firewall settings for port 8020

### Can't Connect to VRChat

1. Ensure VRChat is running with OSC enabled
2. Check VRChat is on the same machine as the MCP server
3. Verify OSC ports 9000-9001 are not blocked
4. Check Windows Firewall allows Python through

### No Avatar Response

1. Verify your avatar supports VRCEmote or gesture parameters
2. Use discovery mode to find supported parameters:
   ```bash
   python tools/mcp/virtual_character/scripts/test_basic_osc.py --mode discover
   ```
3. Check the VRChat console for OSC messages (if debug enabled)

### Network Issues

1. Ensure both machines are on the same network
2. Get Windows machine IP: `ipconfig` (look for IPv4 address)
3. Test connectivity: `ping <windows-ip>` from your dev machine
4. Check Windows Firewall allows incoming connections on port 8020

## Auto-Start on Windows Boot

To automatically start the server when Windows boots:

1. Create a shortcut to `automation\launchers\windows\virtual-character\start_server_windows.bat`
2. Press `Win+R`, type `shell:startup`
3. Copy the shortcut to the Startup folder

Or use Task Scheduler for more control:
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: When computer starts
4. Action: Start a program
5. Program: `powershell.exe`
6. Arguments: `-ExecutionPolicy Bypass -File "C:\path\to\repo\automation\launchers\windows\virtual-character\start_server_windows.ps1" -AutoStart`

## Security Notes

- The server binds to `0.0.0.0` by default (accessible from network)
- Use `127.0.0.1` to restrict to local access only
- Consider using a firewall to restrict access to trusted IPs
- No authentication is currently implemented (add if needed)

## Environment Variables

- `VRCHAT_HOST`: VRChat OSC host (default: 127.0.0.1)
- `VRCHAT_USE_VRCEMOTE`: Enable VRCEmote system (default: true)
- `VRCHAT_MCP_SERVER`: MCP server URL for client scripts

## Example Integration

```python
import aiohttp
import asyncio

async def control_vrchat():
    """Example of controlling VRChat from Python."""
    server_url = "http://192.168.0.152:8020"

    async with aiohttp.ClientSession() as session:
        # Connect to VRChat
        async with session.post(f"{server_url}/set_backend", json={
            "backend": "vrchat_remote",
            "config": {"remote_host": "127.0.0.1", "use_vrcemote": True}
        }) as resp:
            result = await resp.json()
            print(f"Connected: {result['success']}")

        # Send happy emotion (triggers Cheer gesture)
        async with session.post(f"{server_url}/send_animation", json={
            "emotion": "happy"
        }) as resp:
            result = await resp.json()
            print(f"Emotion sent: {result['success']}")

asyncio.run(control_vrchat())
```
