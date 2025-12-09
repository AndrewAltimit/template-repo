# Virtual Character Gestures Reference

## Quick Reference

### Standard Gestures (Direct MCP Call)

| Gesture | MCP Value | VRCEmote | Description |
|---------|-----------|----------|-------------|
| none | `"none"` | 0 | Clear/stop gesture |
| wave | `"wave"` | 1 | Wave hand |
| clap | `"clap"` | 2 | Clapping animation |
| point | `"point"` | 3 | Pointing gesture |
| cheer | `"cheer"` | 4 | Cheering/celebration |
| dance | `"dance"` | 5 | Dance animation |
| **backflip** | `"backflip"` | 6 | Backflip animation |
| sadness | `"sadness"` | 7 | Sad/crying gesture |
| die | `"die"` | 8 | Death/faint animation |

### Usage Examples

#### Direct Gesture Call (Recommended)
```python
# Simple backflip
mcp__virtual-character__send_animation(
    gesture="backflip"
)

# With emotion
mcp__virtual-character__send_animation(
    gesture="backflip",
    emotion="excited",
    emotion_intensity=0.9
)
```

#### Direct VRCEmote Control (Advanced)
```python
# Send specific VRCEmote value
mcp__virtual-character__send_animation(
    parameters={"avatar_params": {"VRCEmote": 6}}  # Backflip
)
```

## VRChat Avatar Wheel Mapping

The standard VRChat avatar gesture wheel layout:

```
        Back (0)
          ↑
    Wave ←   → Point
      (1)     (3)

   Clap ←     → Cheer
     (2)       (4)

  Dance ←     → Backflip
    (5)         (6)

Sadness ←     → Die
    (7)         (8)
```

## Emotion to Gesture Mapping

Some emotions automatically trigger gestures in VRChat:

| Emotion | VRCEmote | Resulting Gesture |
|---------|----------|-------------------|
| neutral | 0 | None |
| happy | 2 | Clap |
| sad | 7 | Sadness |
| angry | 3 | Point (assertive) |
| surprised | 6 | Backflip (excitement) |
| fearful | 8 | Die (dramatic) |
| disgusted | 0 | Clear |

## Toggle Behavior

**Important:** VRChat emotes are **toggle-based**:
- Sending a gesture **activates** it
- Sending the **same** gesture again **deactivates** it
- Sending a **different** gesture replaces the current one
- Some gestures (like backflip) may lock movement while active

## Common Issues & Solutions

### Issue: Gesture not triggering
**Solution:** Check if an emote is already active. Send the same value again to toggle it off first.

### Issue: Movement locked after gesture
**Solution:** Some gestures (backflip, die) lock movement. Toggle the gesture off by sending it again.

### Issue: Wrong gesture plays
**Solution:** Verify the avatar uses the standard gesture wheel. Custom avatars may have different mappings.

## Testing Gestures

Use the test script to verify all gestures work:

```bash
python tools/mcp/mcp_virtual_character/scripts/test_all_gestures.py
```

This will cycle through all available gestures with proper timing and clearing between each.

## Adding Custom Gestures

To add a new gesture:

1. Add to `GestureType` enum in `models/canonical.py`
2. Add mapping in `backends/vrchat_remote.py` VRCEMOTE_GESTURE_MAP
3. Update this documentation
4. Test with the test script

## Performance Tips

- Allow 0.5-1s between gesture changes for smooth transitions
- Clear gestures before movement commands
- Use `reset()` to return to neutral state quickly
- Batch animations with emotions for expressive performances
