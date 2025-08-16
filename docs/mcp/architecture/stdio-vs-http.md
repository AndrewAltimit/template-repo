# MCP Server Transport Modes: STDIO vs HTTP

## The Fundamental Distinction

**STDIO** = **Local Process Communication**
- Server runs on the **same machine** as the client
- Client spawns server as a child process
- Communication via standard input/output streams

**HTTP** = **Remote/Cross-Machine Communication**
- Server runs on a **different machine** or requires special environment
- Server runs independently as a network service
- Communication via HTTP protocol over network

## Critical Understanding

MCP servers support two transport modes that serve fundamentally different purposes based on **where** and **how** the server runs:

### STDIO Mode (Local Process Communication)
- **Purpose**: For **local processes** running on the same machine as the client
- **Configuration**: `.mcp.json`
- **Usage**: `mcp__<server>__<tool>` functions in Claude
- **How it works**: Client spawns the server as a child process and communicates via stdin/stdout
- **Lifecycle**: Started/stopped automatically by the client as needed
- **When to use**: When the server can run in the same environment as the client

### HTTP Mode (Remote/Cross-Machine Communication)
- **Purpose**: For **remote processes** or **cross-machine** communication
- **Configuration**: `docker-compose.yml` or direct server startup
- **Usage**: Direct HTTP calls to `http://host:<port>`
- **How it works**: Runs as a persistent network service
- **Lifecycle**: Started independently, runs continuously
- **When to use**:
  - Server runs on different machine (e.g., `192.168.0.152:8007`)
  - Hardware constraints (e.g., Windows-only software like Gaea2)
  - Software constraints (e.g., GPU requirements for AI models)
  - Resource isolation (e.g., heavy compute workloads)

## Common Confusion Points

### ❌ WRONG: Starting HTTP server for Claude
```bash
# This starts HTTP mode - Claude CANNOT use this!
docker-compose up mcp-content-creation
```

### ✅ RIGHT: Claude uses STDIO automatically
```python
# Claude reads .mcp.json and starts STDIO server automatically
# Just use the tool directly:
result = mcp__content-creation__compile_latex(content="...")
```

## Server-Specific Configurations

### Local-Only Servers (STDIO Preferred)

#### Content Creation Server
- **STDIO**: Auto-started locally by Claude when using `mcp__content-creation__*` tools
- **HTTP**: Available at port 8011 for testing or remote access

#### Code Quality Server
- **STDIO**: Auto-started locally by Claude when using `mcp__code-quality__*` tools
- **HTTP**: Available at port 8010 for testing or remote access

#### Gemini Server
- **STDIO**: Runs locally on host (requires Docker access)
- **HTTP**: Port 8006 for cross-process communication

### Remote/Cross-Machine Servers (HTTP Required)

#### Gaea2 Server
- **Local STDIO**: When Gaea2 is installed locally on Windows
- **Remote HTTP**: `192.168.0.152:8007` when Gaea2 runs on dedicated Windows machine

#### AI Toolkit Server
- **HTTP Only**: `192.168.0.152:8012` (runs on remote machine with GPU)
- **Why**: Requires specific hardware (GPU) and software environment

#### ComfyUI Server
- **HTTP Only**: `192.168.0.152:8013` (runs on remote machine with GPU)
- **Why**: Requires specific hardware (GPU) and software environment

## Volume Mounts and Output Directories

Both modes can use the same output directories:

### STDIO Mode
The `.mcp.json` configuration uses `docker-compose run` which respects volume mounts:
```json
{
  "content-creation": {
    "command": "docker-compose",
    "args": ["run", "--rm", "-T", "mcp-content-creation", ...]
  }
}
```

### HTTP Mode
The `docker-compose.yml` defines persistent volume mounts:
```yaml
volumes:
  - ./outputs/mcp-content:/output
```

Both modes will write to `./outputs/mcp-content/` on the host.

## Troubleshooting

### "mcp__<server>__<tool> not found"
- The MCP server is not connected in this Claude session
- Claude manages STDIO connections automatically
- Try using the tool - Claude should start it

### "Connection refused on port"
- You're trying to use HTTP mode
- For Claude, don't start services manually
- Let Claude handle STDIO connections

### Multiple containers running
- Clean up with: `docker ps | grep mcp | awk '{print $1}' | xargs docker stop`
- Remove stopped containers: `docker container prune`

## Best Practices

1. **For Claude Code**: Never manually start MCP servers
2. **For testing/debugging**: Use HTTP mode with `docker-compose up`
3. **For output files**: Both modes use the same `outputs/` directory
4. **For development**: Edit servers knowing they support both modes

## Summary

- **STDIO = Local Process** - For servers running on the same machine as the client
- **HTTP = Remote/Cross-Machine** - For servers on different machines or with special requirements
- **Claude prefers STDIO** - Automatically manages local servers via `.mcp.json`
- **Use HTTP when necessary** - Remote hardware, Windows-only software, GPU requirements, etc.

## HTTP Mode Technical Implementation

This section provides technical details for implementing and troubleshooting HTTP-based MCP servers using the Streamable HTTP transport specification.

### Overview

The Streamable HTTP transport allows MCP servers to operate as independent HTTP services that can handle multiple client connections. This transport uses HTTP POST and GET requests, with optional Server-Sent Events (SSE) support for streaming.

For the complete specification, see: [MCP Streamable HTTP Transport Specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#streamable-http)

### HTTP Configuration

#### Basic Configuration in .mcp.json

```json
{
  "mcpServers": {
    "your-server": {
      "type": "http",
      "url": "http://localhost:8007/messages"
    }
  }
}
```

**Important**: The URL must point to the `/messages` endpoint, not `/mcp` or other paths.

#### Remote Server Configuration

For servers running on remote machines:

```json
{
  "mcpServers": {
    "gaea2": {
      "type": "http",
      "url": "http://192.168.0.152:8007/messages"
    }
  }
}
```

### Server Implementation Requirements

#### 1. Single Endpoint

The server MUST provide a single HTTP endpoint (e.g., `/messages`) that supports both POST and GET methods.

#### 2. OAuth Discovery (Optional but Recommended)

If your server implements OAuth, ensure these endpoints return consistent URLs:

```python
# OAuth discovery endpoints
@app.get("/.well-known/oauth-authorization-server")
@app.get("/.well-known/oauth-protected-resource")
```

The protected resource URL must match your configured endpoint:
```python
{
    "resource": "http://your-server:port/messages",  # Must match .mcp.json
    "authorization_servers": ["http://your-server:port"]
}
```

#### 3. Session Management

The server should generate and return a session ID during initialization:

```python
# Generate session ID on initialize request
if method == "initialize" and not session_id:
    session_id = str(uuid.uuid4())

# Return in response headers
headers = {
    "Mcp-Session-Id": session_id
}
```

#### 4. Protocol Version Handling

Echo back the client's requested protocol version:

```python
return {
    "protocolVersion": params["protocolVersion"],  # Echo client's version
    "serverInfo": {"name": "Your Server", "version": "1.0.0"},
    "capabilities": {
        "tools": {"listChanged": True},
        "resources": {},  # Use {} not null/None
        "prompts": {}     # Use {} not null/None
    }
}
```

#### 5. Notification Handling

Notifications (requests without an `id` field) MUST return 202 Accepted with no body:

```python
if request_id is None:  # This is a notification
    return Response(status_code=202, headers={"Mcp-Session-Id": session_id})
```

### Complete Connection Flow

1. **OAuth Discovery** (if applicable)
   ```
   GET /.well-known/oauth-authorization-server
   GET /.well-known/oauth-protected-resource
   ```

2. **OAuth Flow** (if applicable)
   ```
   POST /register
   GET /authorize → 302 Redirect
   POST /token
   ```

3. **MCP Initialization**
   ```
   POST /messages
   {
     "jsonrpc": "2.0",
     "method": "initialize",
     "params": {
       "protocolVersion": "2025-06-18",
       "capabilities": {"roots": {}},
       "clientInfo": {"name": "claude-code", "version": "1.0.61"}
     },
     "id": 0
   }
   ```

4. **Server Response with Session ID**
   ```
   Headers: Mcp-Session-Id: <generated-uuid>
   {
     "jsonrpc": "2.0",
     "result": {
       "protocolVersion": "2025-06-18",
       "serverInfo": {...},
       "capabilities": {...}
     },
     "id": 0
   }
   ```

5. **Client Sends Initialized Notification**
   ```
   POST /messages
   Headers: Mcp-Session-Id: <uuid>, MCP-Protocol-Version: 2025-06-18
   {
     "jsonrpc": "2.0",
     "method": "notifications/initialized"
   }
   ```
   Server returns: 202 Accepted

6. **Client Lists Tools**
   ```
   POST /messages
   Headers: Mcp-Session-Id: <uuid>, MCP-Protocol-Version: 2025-06-18
   {
     "jsonrpc": "2.0",
     "method": "tools/list",
     "id": 1
   }
   ```

### HTTP Mode Troubleshooting

#### Issue: "Protected resource does not match expected URL"

**Solution**: Ensure your OAuth discovery endpoint returns the exact URL configured in `.mcp.json`:

```python
async def oauth_protected_resource(request):
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    return {
        "resource": f"{base_url}/messages",  # Must match .mcp.json
        "authorization_servers": [base_url]
    }
```

#### Issue: Client doesn't proceed after initialization

**Possible causes**:
1. Returning `null` instead of `{}` for empty capabilities
2. Not generating/returning a session ID
3. Not handling notifications correctly (must return 202)
4. Hardcoding protocol version instead of echoing client's version

#### Issue: 404 on OAuth endpoints

**Solution**: Add all necessary OAuth discovery endpoints:

```python
app.get("/.well-known/oauth-authorization-server")(oauth_discovery)
app.get("/.well-known/oauth-authorization-server/messages")(oauth_discovery)
app.get("/.well-known/oauth-protected-resource")(oauth_protected_resource)
```

### Testing Your HTTP Server

Use this test script to verify your server implementation:

```python
#!/usr/bin/env python3
import json
import requests

SERVER_URL = "http://localhost:8007"

# 1. Initialize
response = requests.post(f"{SERVER_URL}/messages", json={
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {"roots": {}},
        "clientInfo": {"name": "test-client", "version": "1.0"}
    },
    "id": 0
})
print(f"Initialize: {response.status_code}")
session_id = response.headers.get("Mcp-Session-Id")
print(f"Session ID: {session_id}")

# 2. Send notification
headers = {"Mcp-Session-Id": session_id}
response = requests.post(f"{SERVER_URL}/messages",
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
)
print(f"Notification: {response.status_code} (should be 202)")

# 3. List tools
response = requests.post(f"{SERVER_URL}/messages",
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    }
)
print(f"Tools: {response.status_code}")
if response.status_code == 200:
    tools = response.json()["result"]["tools"]
    print(f"Found {len(tools)} tools")
```

### Security Considerations

1. **Validate Origin headers** to prevent DNS rebinding attacks
2. **Bind to localhost** when running locally
3. **Implement proper authentication** for production use
4. **Use HTTPS** for remote servers when possible

### References

- [MCP Streamable HTTP Transport Specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#streamable-http)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [Server-Sent Events (SSE) Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
