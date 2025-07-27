# MCP Core Components

The MCP Core module provides shared base classes and utilities for building Model Context Protocol (MCP) servers. All MCP servers in this repository inherit from these core components to ensure consistency and code reuse.

## Overview

The MCP Core module consists of four main components:

1. **BaseMCPServer**: Abstract base class for all MCP servers
2. **HTTPBridge**: HTTP bridge for forwarding requests to remote MCP servers
3. **ClientRegistry**: Client registration and management (currently disabled for home lab use)
4. **Utilities**: Common utility functions for logging, configuration, and environment management

## Components

### BaseMCPServer

The `BaseMCPServer` class provides the foundation for all MCP servers with:

- **Common HTTP routes**: `/health`, `/mcp/tools`, `/mcp/execute`, `/messages`, `/register`, `/authorize`, `/token`
- **Tool registration and execution framework**
- **Support for both HTTP and stdio modes**
- **Automatic error handling and response formatting**
- **FastAPI integration for HTTP mode**
- **OAuth2-style authentication bypass for simplified home lab use**
- **JSON-RPC 2.0 support for MCP protocol**
- **HTTP Stream Transport with SSE support**

**Key Features:**
- Abstract `get_tools()` method that subclasses must implement
- Automatic tool discovery and validation
- Unified request/response models
- Built-in health checks
- Logging setup
- MCP protocol discovery endpoints
- Session management for streaming responses

**Usage Example:**
```python
from tools.mcp.core import BaseMCPServer, setup_logging
from typing import Dict, Any

class MyMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(
            name="My MCP Server",
            version="1.0.0",
            port=8020
        )
        self.logger = setup_logging("MyMCP")

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "my_tool": {
                "description": "Does something useful",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"}
                    },
                    "required": ["input"]
                }
            }
        }

    async def my_tool(self, input: str) -> Dict[str, Any]:
        # Tool implementation
        return {"result": f"Processed: {input}"}
```

### HTTPBridge

The `HTTPBridge` class enables forwarding MCP requests to remote servers:

- **Remote server proxying**: Forward requests to MCP servers on different hosts
- **CORS support**: Enable cross-origin requests
- **Timeout handling**: Configurable request timeouts
- **Health monitoring**: Check remote server availability

**Key Features:**
- Transparent request forwarding
- Error handling and logging
- FastAPI-based implementation
- Support for `/health`, `/mcp/tools`, `/mcp/execute` endpoints
- Environment variable configuration support

**Usage Example:**
```python
from tools.mcp.core import HTTPBridge
import uvicorn

# Create bridge to remote MCP server
bridge = HTTPBridge(
    service_name="Remote Gaea2",
    remote_url="http://192.168.0.152:8007",
    port=8080,
    timeout=60,
    enable_cors=True
)

# Run the bridge
if __name__ == "__main__":
    uvicorn.run(bridge.app, host="0.0.0.0", port=bridge.port)
```

### ClientRegistry (Currently Disabled)

The `ClientRegistry` class provides client management functionality (currently disabled for home lab use):

- **Client registration**: Track and manage MCP clients
- **Persistent storage**: Store client information in JSON
- **Activity tracking**: Monitor client usage and last seen times
- **Statistics**: Track request counts and active clients

**Note**: In the current implementation, client registry functionality is commented out in `BaseMCPServer` for simplified home lab deployment. Registration endpoints return mock responses without actual tracking.

### Utilities

Common utility functions used across all MCP servers:

#### setup_logging(name: str, level: str = "INFO") -> logging.Logger
Configure standardized logging for MCP servers.

**Parameters:**
- `name`: Logger name (typically the server name)
- `level`: Logging level (DEBUG, INFO, WARNING, ERROR)

**Example:**
```python
from tools.mcp.core import setup_logging

logger = setup_logging("MyMCPServer", "DEBUG")
logger.info("Server starting...")
```

#### validate_environment(required_vars: List[str]) -> Dict[str, str]
Validate that required environment variables are set.

**Parameters:**
- `required_vars`: List of required environment variable names

**Example:**
```python
from tools.mcp.core import validate_environment

# Ensure API key is set
env_vars = validate_environment(["OPENAI_API_KEY", "GAEA2_PATH"])
api_key = env_vars["OPENAI_API_KEY"]
```

#### ensure_directory(path: str) -> str
Ensure a directory exists, creating it if necessary.

**Parameters:**
- `path`: Directory path to create/verify

**Example:**
```python
from tools.mcp.core.utils import ensure_directory

output_dir = ensure_directory("/app/output/renders")
```

#### load_config(config_path: Optional[str] = None) -> Dict[str, Any]
Load configuration from JSON file.

**Parameters:**
- `config_path`: Path to config file (defaults to searching for .mcp.json)

**Search order:**
1. `.mcp.json` in current directory
2. `~/.mcp.json` in user home
3. `/etc/mcp/config.json` system-wide

**Example:**
```python
from tools.mcp.core.utils import load_config

config = load_config()
port = config.get("port", 8000)
```

#### check_container_environment() -> bool
Check if the server is running inside a Docker container.

**Example:**
```python
from tools.mcp.core.utils import check_container_environment

if check_container_environment():
    print("Running in Docker")
else:
    print("Running on host")
```

#### create_bridge_from_env(service_name: str, default_port: int = 8191) -> HTTPBridge
Create an HTTP bridge using environment variables for configuration.

**Environment Variables:**
- `REMOTE_MCP_URL`: Remote MCP server URL
- `TIMEOUT`: Request timeout in seconds
- `PORT`: Port to listen on (optional)

**Example:**
```python
from tools.mcp.core.http_bridge import create_bridge_from_env

# Create bridge using environment variables
bridge = create_bridge_from_env("MyService", default_port=8080)
bridge.run()
```

**Note**: The core module exports only the most commonly used components: `BaseMCPServer`, `HTTPBridge`, `setup_logging`, and `validate_environment`. Other utilities like `ensure_directory`, `load_config`, and `check_container_environment` must be imported directly from `tools.mcp.core.utils`.

## Creating a New MCP Server

To create a new MCP server using the core components:

1. **Create server class inheriting from BaseMCPServer:**

```python
from tools.mcp.core import BaseMCPServer, setup_logging
from typing import Dict, Any

class MyNewMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(
            name="My New MCP Server",
            version="1.0.0",
            port=8030  # Choose unique port
        )
        self.logger = setup_logging("MyNewMCP")

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available tools"""
        return {
            "tool_name": {
                "description": "Tool description",
                "parameters": {
                    # JSON Schema for parameters
                }
            }
        }

    async def tool_name(self, **kwargs) -> Dict[str, Any]:
        """Implement tool logic"""
        return {"result": "success"}
```

2. **Create server.py with run modes:**

```python
import argparse
import asyncio
import uvicorn

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["stdio", "http"], default="http")
    parser.add_argument("--port", type=int, default=8030)
    args = parser.parse_args()

    server = MyNewMCPServer()

    if args.mode == "stdio":
        # Run in stdio mode for Claude Desktop
        import mcp.server.stdio
        mcp_server = mcp.server.Server(server.name)

        # Register tools
        for tool_name in server.get_tools():
            mcp_server.add_tool(getattr(server, tool_name))

        asyncio.run(mcp_server.run())
    else:
        # Run in HTTP mode
        uvicorn.run(server.app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    main()
```

3. **Add to docker-compose.yml:**

```yaml
my-new-mcp:
  build:
    context: .
    dockerfile: docker/Dockerfile.mcp
  ports:
    - "8030:8030"
  environment:
    - MCP_MODE=http
  volumes:
    - ./tools/mcp/my_new:/app/my_new
```

## Request/Response Models

### HTTP API Models

#### ToolRequest
Standard request format for tool execution via HTTP API:

```python
{
    "tool": "tool_name",
    "arguments": {
        "param1": "value1",
        "param2": "value2"
    }
}
```

Note: Both `arguments` and `parameters` fields are supported for backwards compatibility.

#### ToolResponse
Standard response format:

```python
{
    "success": true,
    "result": {
        # Tool-specific result data
    },
    "error": null  # Error message if success is false
}
```

### JSON-RPC 2.0 Models (MCP Protocol)

The server also supports JSON-RPC 2.0 for MCP protocol communication:

#### Initialize Request
```json
{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "clientInfo": {
            "name": "claude-code",
            "version": "1.0"
        }
    },
    "id": 1
}
```

#### Tools List Request
```json
{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 2
}
```

#### Tool Call Request
```json
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "tool_name",
        "arguments": {
            "param1": "value1"
        }
    },
    "id": 3
}
```

### HTTP Stream Transport

The server supports HTTP Stream Transport via the `/messages` endpoint with optional Server-Sent Events (SSE) for streaming responses. Set the `Mcp-Response-Mode: stream` header to enable streaming.

## Best Practices

1. **Always inherit from BaseMCPServer** for consistency
2. **Use setup_logging()** for standardized log formatting
3. **Validate environment variables** early in initialization
4. **Handle errors gracefully** and return meaningful error messages
5. **Document tool parameters** using JSON Schema
6. **Choose unique ports** to avoid conflicts (8000-8099 range)
7. **Support both HTTP and stdio modes** when possible
8. **Use type hints** for better code clarity

## Testing

When testing MCP servers built with core components:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_list_tools():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get("/mcp/tools")
        assert response.status_code == 200
        assert "tools" in response.json()
```

## Available Endpoints

### Core Endpoints
- `GET /health` - Health check endpoint
- `GET /mcp/tools` - List available tools
- `POST /mcp/execute` - Execute a tool
- `GET /mcp/clients` - List registered clients (returns empty for home lab)
- `GET /mcp/stats` - Get server statistics

### MCP Protocol Endpoints
- `GET /messages` - MCP server information
- `POST /messages` - Handle MCP JSON-RPC requests (supports streaming)
- `GET /mcp` - SSE endpoint for streaming
- `POST /mcp` - JSON-RPC endpoint (legacy)
- `GET /mcp/capabilities` - Server capabilities
- `POST /mcp/initialize` - Initialize MCP session

### OAuth2-style Endpoints (Bypass Mode)
- `POST /register` - Client registration
- `GET/POST /authorize` - OAuth authorization (auto-approves)
- `POST /token` - Token exchange (returns bypass token)

### Discovery Endpoints
- `GET /.well-known/mcp` - MCP protocol discovery
- `GET /.well-known/oauth-authorization-server` - OAuth discovery

## Environment Configuration

Common environment variables used by MCP servers:

- `MCP_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `MCP_CONFIG_PATH`: Path to configuration file
- `MCP_TIMEOUT`: Default timeout for operations
- `MCP_MAX_RETRIES`: Maximum retry attempts

For HTTPBridge:
- `REMOTE_MCP_URL`: Remote MCP server URL
- `TIMEOUT`: Request timeout in seconds
- `PORT`: Port to listen on

## Security Considerations

- **Input validation**: Always validate tool parameters
- **Authentication**: Implement if exposing to public networks
- **Rate limiting**: Consider adding for public endpoints
- **CORS configuration**: Configure appropriately for your use case
- **Secrets management**: Never hardcode sensitive data

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure each server uses a unique port
2. **Import errors**: Check PYTHONPATH includes the project root
3. **Missing dependencies**: Install required packages with pip
4. **Container permissions**: Ensure proper user permissions in Docker

### Debug Mode

Enable debug logging for detailed information:

```python
logger = setup_logging("MyMCP", "DEBUG")
```

Or set environment variable:
```bash
export MCP_LOG_LEVEL=DEBUG
```

## Contributing

When adding new core functionality:

1. Ensure backwards compatibility
2. Add comprehensive docstrings
3. Include type hints
4. Write unit tests
5. Update this documentation

## License

See the repository's main LICENSE file for licensing information.
