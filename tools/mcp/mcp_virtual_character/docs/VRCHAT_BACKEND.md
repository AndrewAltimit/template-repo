# VRChat Backend Documentation

## Overview

The VRChat backend allows control of VRChat avatars through OSC (Open Sound Control) protocol. This enables AI agents to embody and control avatars in VRChat worlds.

## Requirements

### Software Requirements

1. **VRChat** - Must be running with OSC enabled
2. **Python Dependencies**:
   ```bash
   pip install python-osc
   ```

### VRChat Setup

1. **Enable OSC in VRChat**:
   - Open VRChat
   - Go to Settings → OSC → Enable
   - Note: OSC is enabled per-avatar, not globally

2. **Avatar Requirements**:
   - Avatar must have OSC-compatible parameters
   - Standard emotion and gesture parameters recommended
   - Custom parameters can be added

### Network Configuration

- **Default Ports**:
  - VRChat receives OSC on port 9000
  - VRChat sends OSC on port 9001
  - These can be configured if needed

## Testing

### Direct Backend Test

Test the VRChat backend directly without the MCP server:

```bash
# Test from the same machine as VRChat
python tools/mcp/virtual_character/scripts/test_vrchat.py --host 127.0.0.1

# Test from remote machine
python tools/mcp/virtual_character/scripts/test_vrchat.py --host 192.168.0.152

# Run specific test
python tools/mcp/virtual_character/scripts/test_vrchat.py --test emotions
python tools/mcp/virtual_character/scripts/test_vrchat.py --test movement
python tools/mcp/virtual_character/scripts/test_vrchat.py --test circle

# Interactive control mode
python tools/mcp/virtual_character/scripts/test_vrchat.py --test interactive
```

### MCP Server Test

Test through the MCP server interface:

```bash
# Start the MCP server
python -m tools.mcp.virtual_character.server

# In another terminal, run the MCP test
python tools/mcp/virtual_character/scripts/test_vrchat_mcp.py \
  --vrchat-host 192.168.0.152

# Test specific features
python tools/mcp/virtual_character/scripts/test_vrchat_mcp.py --test emotions
python tools/mcp/virtual_character/scripts/test_vrchat_mcp.py --test movement
```

## Avatar Parameters

### Standard OSC Parameters

The backend uses these standard VRChat OSC addresses:

#### Emotions
- `/avatar/parameters/EmotionNeutral` (float 0-1)
- `/avatar/parameters/EmotionHappy` (float 0-1)
- `/avatar/parameters/EmotionSad` (float 0-1)
- `/avatar/parameters/EmotionAngry` (float 0-1)
- `/avatar/parameters/EmotionSurprised` (float 0-1)
- `/avatar/parameters/EmotionFearful` (float 0-1)

#### Gestures
- `/avatar/parameters/GestureLeft` (int 0-7)
- `/avatar/parameters/GestureRight` (int 0-7)
- `/avatar/parameters/GestureWeight` (float 0-1)

Gesture IDs:
- 0: None
- 1: Wave
- 2: Point
- 3: Thumbs Up
- 4: Nod
- 5: Shake Head
- 6: Clap
- 7: Dance

#### Movement
- `/input/Vertical` (float -1 to 1) - Forward/backward
- `/input/Horizontal` (float -1 to 1) - Left/right strafe
- `/input/LookHorizontal` (float -1 to 1) - Turn left/right
- `/input/LookVertical` (float -1 to 1) - Look up/down
- `/input/Jump` (bool) - Jump action
- `/input/Run` (bool) - Run modifier
- `/input/Crouch` (bool) - Crouch state

#### Other Parameters
- `/avatar/parameters/Sitting` (bool)
- `/avatar/parameters/Crouching` (bool)
- `/avatar/parameters/AFK` (bool)

### Custom Parameters

You can send custom avatar parameters:

```python
animation = CanonicalAnimationData()
animation.parameters = {
    "avatar_params": {
        "CustomParam1": 0.5,
        "CustomParam2": True,
        "CustomParam3": 42
    }
}
```

## Usage Examples

### Python Client

```python
import asyncio
from tools.mcp.virtual_character.backends.vrchat_remote import VRChatRemoteBackend
from tools.mcp.virtual_character.models.canonical import (
    CanonicalAnimationData,
    EmotionType,
    GestureType
)

async def control_avatar():
    # Create backend
    backend = VRChatRemoteBackend()

    # Connect
    await backend.connect({
        "remote_host": "192.168.0.152",
        "osc_in_port": 9000,
        "osc_out_port": 9001
    })

    # Set emotion
    animation = CanonicalAnimationData()
    animation.emotion = EmotionType.HAPPY
    animation.emotion_intensity = 1.0
    await backend.send_animation_data(animation)

    # Perform gesture
    animation.gesture = GestureType.WAVE
    await backend.send_animation_data(animation)

    # Move forward
    animation.parameters = {"move_forward": 1.0}
    await backend.send_animation_data(animation)
    await asyncio.sleep(2)

    # Stop
    animation.parameters = {"move_forward": 0.0}
    await backend.send_animation_data(animation)

    # Disconnect
    await backend.disconnect()

asyncio.run(control_avatar())
```

### MCP Server Usage

```python
import aiohttp
import asyncio

async def control_via_mcp():
    async with aiohttp.ClientSession() as session:
        # Connect to VRChat backend
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "set_backend",
                "parameters": {
                    "backend": "vrchat_remote",
                    "config": {
                        "remote_host": "192.168.0.152"
                    }
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

asyncio.run(control_via_mcp())
```

## Troubleshooting

### Connection Issues

1. **Cannot connect to VRChat**:
   - Verify VRChat is running and OSC is enabled
   - Check firewall settings for ports 9000/9001
   - Ensure correct IP address if connecting remotely

2. **Animations not working**:
   - Verify avatar has OSC parameters
   - Check avatar parameter names match expected format
   - Some avatars may use different parameter names

3. **Movement not working**:
   - Movement inputs require the avatar to be in a world
   - Some worlds may restrict movement
   - Desktop mode has different movement behavior than VR

### Performance

- OSC messages are UDP, so they're fast but not guaranteed
- Rapid parameter changes may be dropped
- Consider adding small delays between commands

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Monitor OSC messages:
- Use OSC monitoring tools to see messages being sent/received
- Check VRChat's OSC debug menu (if available)

## Advanced Features

### Bridge Server (Future)

A bridge server can be implemented for:
- Video capture via OBS
- Audio streaming
- Advanced state tracking
- Multiple avatar control

### World Integration

Future features could include:
- World object interaction
- Portal/world switching
- Multi-user coordination
- Event responses

## Limitations

1. **OSC Limitations**:
   - One-way for most parameters (send only)
   - Limited state feedback from VRChat
   - No direct world information

2. **Avatar Dependent**:
   - Features depend on avatar capabilities
   - Not all avatars support all parameters
   - Custom avatars may need configuration

3. **Network**:
   - Requires network access between controller and VRChat
   - UDP protocol means no delivery confirmation
   - Firewall configuration may be needed
