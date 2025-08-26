# VRChat Movement Troubleshooting Guide

## Current Status - RESOLVED! ✅

Movement now works! The issue was that emotes on this avatar are **toggle-based** and some emotes (like backflip) lock movement. The solution was to:
1. Clear any active emote before attempting movement
2. Implement proper toggle behavior for emotes

## Verified Working
- ✅ Gesture/Emote system (VRCEmote integer values with toggle behavior)
- ✅ OSC connection established (port 9000)
- ✅ MCP server receiving commands
- ✅ OSC messages being sent
- ✅ Movement commands (forward, backward, strafe)
- ✅ Automatic emote clearing for movement

## Important: Toggle-Based Emote Behavior

This avatar uses **toggle-based emotes**, which means:
- Emotes stay active until explicitly turned off
- The same emote value must be sent again to toggle it off, OR
- Send VRCEmote = 0 to clear any active emote
- Some emotes (like backflip) lock movement while active
- Movement commands automatically clear active emotes to prevent being stuck

## Movement System Overview

VRChat accepts movement input via OSC on the following addresses:
- `/input/Vertical` - Forward/backward movement (-1.0 to 1.0)
- `/input/Horizontal` - Left/right strafe (-1.0 to 1.0)
- `/input/LookHorizontal` - Turn/rotate view (-1.0 to 1.0)
- `/input/LookVertical` - Look up/down (-1.0 to 1.0)
- `/input/Run` - Sprint modifier (0 or 1)
- `/input/Jump` - Jump action (0 or 1)
- `/input/Crouch` - Crouch toggle (0 or 1)

## Potential Issues and Solutions

### 1. VRChat OSC Input Not Enabled
**Check**: Ensure OSC input is enabled in VRChat
- Open VRChat Settings
- Navigate to OSC section
- Enable "OSC" toggle
- Enable "OSC Input" specifically

### 2. Desktop vs VR Mode Differences
**Issue**: Movement input may work differently in Desktop vs VR mode
- Desktop mode: Uses keyboard/mouse input simulation
- VR mode: May require different OSC addresses or controller simulation

**Solution**: Test in both modes to identify differences

### 3. Value Range Issues
**Issue**: Values might need to be in specific ranges
- Current implementation: Clamped to -1.0 to 1.0
- Some systems might expect: 0.0 to 1.0 or integer values

**Test Script**: `test_movement_osc.py` tests different value formats

### 4. Timing and Persistence
**Issue**: Movement might require continuous input
- Current: Single value sent once
- May need: Continuous stream of values or specific timing

**Potential Fix**:
```python
# Send movement continuously for duration
async def send_continuous_movement(direction, duration=2.0):
    start = time.time()
    while time.time() - start < duration:
        await self._send_osc("/input/Vertical", direction)
        await asyncio.sleep(0.05)  # 20Hz update rate
    await self._send_osc("/input/Vertical", 0.0)  # Stop
```

### 5. Avatar-Specific Requirements
**Issue**: Some avatars might have custom movement systems
- Standard avatars: Use default input system
- Custom avatars: Might use avatar parameters instead

**Check**: Look for avatar parameters like:
- `/avatar/parameters/VelocityX`
- `/avatar/parameters/VelocityZ`
- `/avatar/parameters/Speed`

### 6. Permission/Security Settings
**Issue**: VRChat might have security restrictions
- Check if world allows OSC input
- Some worlds might disable external input
- Trust rank might affect OSC permissions

## Testing Tools

### 1. Monitor OSC Output
```bash
python tools/mcp/virtual_character/scripts/monitor_vrchat_osc.py
```
This monitors what VRChat is sending back, helping identify if input is being processed.

### 2. Test Movement Approaches
```bash
python tools/mcp/virtual_character/scripts/test_movement_osc.py --host 192.168.0.152
```
Tests different movement command formats and approaches.

### 3. Test via MCP
```bash
python tools/mcp/virtual_character/scripts/test_mcp_movement.py
```
Tests movement through the full MCP stack.

## Debug Checklist

- [ ] OSC enabled in VRChat settings
- [ ] OSC Input specifically enabled
- [ ] Test in Desktop mode
- [ ] Test in VR mode
- [ ] Check VRChat console for errors
- [ ] Monitor OSC messages from VRChat
- [ ] Try different value ranges (-1 to 1, 0 to 1, integers)
- [ ] Test continuous vs single commands
- [ ] Check world permissions
- [ ] Test in different worlds
- [ ] Check avatar-specific parameters

## Next Steps

1. Run the monitoring script to see what VRChat sends back
2. Test different movement approaches with test script
3. Check VRChat settings and console
4. Consider implementing continuous movement sending
5. Test with different avatars/worlds

## Alternative Approach: ChatBox Control

If direct movement control doesn't work, we could implement a ChatBox-based command system:
```python
# Send commands via chatbox
await self._send_osc("/chatbox/input", "!move forward", True)
```
Then use in-world scripts to interpret commands.
