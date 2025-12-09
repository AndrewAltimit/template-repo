# VRChat OSC Setup Guide

## Port Configuration

**IMPORTANT**: The port naming can be confusing. Here's what they actually mean:

- `osc_in_port`: The port to send messages **INTO** VRChat (default: 9000)
  - This is where VRChat **receives** OSC messages
  - Your MCP server sends to this port

- `osc_out_port`: The port to receive messages **OUT OF** VRChat (default: 9001)
  - This is where VRChat **sends** OSC messages
  - Your MCP server listens on this port

## Correct Configuration

When setting up the VRChat backend, use:

```python
{
  "remote_host": "127.0.0.1",  # Use 127.0.0.1 if VRChat is on same machine
  "osc_in_port": 9000,          # VRChat receives here
  "osc_out_port": 9001,         # VRChat sends here
  "use_vrcemote": true          # Most avatars use VRCEmote system
}
```

## Common Issues

### No Movement Despite Successful Commands

1. **Check if a local server is running**:
   ```bash
   ps aux | grep virtual.character
   ```
   Kill any local instances if you want to use the remote server.

2. **Verify port configuration**:
   - The server logs should show: `Connected to VRChat at 127.0.0.1:9000`
   - NOT: `Connected to VRChat at 127.0.0.1:9001`

3. **Test with the direct script**:
   ```bash
   python tools/mcp/mcp_virtual_character/scripts/test_vrchat.py
   ```
   This bypasses the MCP layer and tests OSC directly.

## Network Topology

- If MCP server and VRChat are on the **same machine**: Use `remote_host: "127.0.0.1"`
- If MCP server and VRChat are on **different machines**: Use the VRChat machine's IP

## Testing

After configuration, test with:

```python
# Simple wave
mcp__virtual-character__send_animation(gesture="wave")

# Jump
mcp__virtual-character__send_animation(parameters={"jump": true})

# Complex animation
mcp__virtual-character__send_animation(
    emotion="happy",
    gesture="dance",
    parameters={"move_forward": 1, "duration": 2}
)
```
