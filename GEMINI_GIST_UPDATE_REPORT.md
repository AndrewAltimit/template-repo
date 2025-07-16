# Gemini MCP Gist Update Report

Based on our latest implementation, here are the recommended updates to incorporate into your gist:

## Important Note: Two Implementation Approaches

We provide two different implementations of the Gemini MCP server, each with its own trade-offs:

### 1. **HTTP-based Server (FastAPI)** - Simplified, standalone
- ✅ Easy to test and debug
- ✅ Can be accessed from any HTTP client
- ✅ Good for development and testing
- ❌ No streaming support
- ❌ Request/response model only

### 2. **stdio-based Server (MCP Protocol)** - Full-featured, original
- ✅ Streaming support for real-time responses
- ✅ Bidirectional communication
- ✅ Full MCP protocol compliance
- ✅ Auto-consultation on uncertainty detection
- ❌ Requires MCP client for testing
- ❌ More complex to debug

## 1A. HTTP-based Gemini MCP Server (Simplified)

**New File Option A: `gemini_mcp_server.py` (HTTP version)**

This is a simplified standalone server that runs on port 8006 with HTTP API.

<details>
<summary>Full HTTP server content</summary>

```python
#!/usr/bin/env python3
"""
Gemini MCP Server - Standalone server for Gemini CLI integration.

This server MUST run on the host system, not in a container, as the Gemini CLI
requires Docker access and would need complex Docker-in-Docker setup otherwise.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# Check if running in container BEFORE any other imports or operations
def check_container_and_exit():
    """Check if running in a container and exit immediately if true."""
    if os.path.exists("/.dockerenv") or os.environ.get("CONTAINER_ENV"):
        print("ERROR: Gemini MCP Server cannot run inside a container!", file=sys.stderr)
        print(
            "The Gemini CLI requires Docker access and must run on the host system.",
            file=sys.stderr,
        )
        print("Please launch this server directly on the host with:", file=sys.stderr)
        print("  python tools/mcp/gemini_mcp_server.py", file=sys.stderr)
        sys.exit(1)


# Perform container check immediately
check_container_and_exit()

# Import Gemini integration after container check
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.gemini.gemini_integration import GeminiIntegration  # noqa: E402

app = FastAPI(title="Gemini MCP Server", version="1.0.0")

# Initialize Gemini integration
gemini = GeminiIntegration()


class ConsultGeminiRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None
    max_retries: Optional[int] = 3


class ConsultGeminiResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str


class ClearHistoryResponse(BaseModel):
    message: str
    cleared_count: int


@app.get("/")
async def root():
    """Root endpoint providing server information."""
    return {
        "name": "Gemini MCP Server",
        "version": "1.0.0",
        "description": "Standalone MCP server for Gemini CLI integration",
        "status": "running",
        "note": "This server must run on the host system, not in a container",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/tools/consult_gemini", response_model=ConsultGeminiResponse)
async def consult_gemini(request: ConsultGeminiRequest):
    """
    Consult Gemini AI for assistance with a given prompt.

    This tool uses the Gemini CLI which requires Docker access,
    so it must run on the host system.
    """
    try:
        # Use the existing GeminiIntegration
        # Convert context dict to JSON string if provided
        context_str = ""
        if request.context:
            context_str = json.dumps(request.context, indent=2)

        result = await gemini.consult_gemini(
            request.prompt,
            context=context_str,
            comparison_mode=True,
            force_consult=False,
        )

        return ConsultGeminiResponse(
            response=result.get("response", ""),
            conversation_id=result.get("consultation_id", ""),
            timestamp=result.get("timestamp", datetime.utcnow().isoformat()),
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini CLI command failed: {e.stderr if hasattr(e, 'stderr') else str(e)}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/clear_gemini_history", response_model=ClearHistoryResponse)
async def clear_gemini_history():
    """
    Clear Gemini conversation history for fresh responses.

    This is useful when you want to start a new conversation context
    without influence from previous interactions.
    """
    try:
        result = gemini.clear_conversation_history()
        cleared_count = result.get("cleared_entries", 0)

        return ClearHistoryResponse(
            message="Gemini conversation history cleared successfully",
            cleared_count=cleared_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mcp/tools")
async def list_tools():
    """List available MCP tools provided by this server."""
    return {
        "tools": [
            {
                "name": "consult_gemini",
                "description": "Consult Gemini AI for assistance (requires host execution)",
                "input_schema": ConsultGeminiRequest.schema(),
            },
            {
                "name": "clear_gemini_history",
                "description": "Clear Gemini conversation history",
                "input_schema": {},
            },
        ]
    }


if __name__ == "__main__":
    # Double-check we're not in a container before starting
    check_container_and_exit()

    # Run on port 8006 to avoid conflict with main MCP server
    port = int(os.environ.get("GEMINI_MCP_PORT", "8006"))
    host = os.environ.get("GEMINI_MCP_HOST", "127.0.0.1")

    print(f"Starting Gemini MCP Server on {host}:{port}")
    print("NOTE: This server must run on the host system, not in a container")

    uvicorn.run(app, host=host, port=port)
```
</details>

## 1B. stdio-based Gemini MCP Server (Full-featured)

**New File Option B: `gemini_mcp_server_stdio.py` (stdio version)**

This is the full-featured MCP server with streaming support, auto-consultation, and advanced configuration.

<details>
<summary>Full stdio server content (recommended for production)</summary>

```python
#!/usr/bin/env python3
"""
MCP Server with Gemini Integration
Provides development workflow automation with AI second opinions
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server, InitializationOptions

# Assuming gemini_integration.py is in the same directory or properly installed
from gemini_integration import get_integration


class MCPServer:
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.server = Server("gemini-mcp-server")

        # Initialize Gemini integration with singleton pattern
        self.gemini_config = self._load_gemini_config()
        # Get the singleton instance, passing config on first call
        self.gemini = get_integration(self.gemini_config)

        # Track uncertainty for auto-consultation
        self.last_response_uncertainty = None

        self._setup_tools()

    def _load_gemini_config(self) -> Dict[str, Any]:
        """Load Gemini configuration from environment or config file."""
        # Try to load .env file if it exists
        env_file = self.project_root / '.env'
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
            except Exception as e:
                print(f"Warning: Could not load .env file: {e}")

        config = {
            'enabled': os.getenv('GEMINI_ENABLED', 'true').lower() == 'true',
            'auto_consult': os.getenv('GEMINI_AUTO_CONSULT', 'true').lower() == 'true',
            'cli_command': os.getenv('GEMINI_CLI_COMMAND', 'gemini'),
            'timeout': int(os.getenv('GEMINI_TIMEOUT', '60')),
            'rate_limit_delay': float(os.getenv('GEMINI_RATE_LIMIT', '2')),
            'max_context_length': int(os.getenv('GEMINI_MAX_CONTEXT', '4000')),
            'log_consultations': os.getenv('GEMINI_LOG_CONSULTATIONS', 'true').lower() == 'true',
            'model': os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
            'sandbox_mode': os.getenv('GEMINI_SANDBOX', 'false').lower() == 'true',
            'debug_mode': os.getenv('GEMINI_DEBUG', 'false').lower() == 'true',
            'include_history': os.getenv('GEMINI_INCLUDE_HISTORY', 'true').lower() == 'true',
            'max_history_entries': int(os.getenv('GEMINI_MAX_HISTORY', '10')),
        }

        # Try to load from config file
        config_file = self.project_root / 'gemini-config.json'
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                config.update(file_config)
            except Exception as e:
                print(f"Warning: Could not load gemini-config.json: {e}")

        return config

    def _setup_tools(self):
        """Register all MCP tools"""

        # Gemini consultation tool
        @self.server.call_tool()
        async def consult_gemini(arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Consult Gemini CLI for a second opinion or validation."""
            query = arguments.get('query', '')
            context = arguments.get('context', '')
            comparison_mode = arguments.get('comparison_mode', True)
            force_consult = arguments.get('force', False)

            if not query:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: 'query' parameter is required for Gemini consultation"
                )]

            # Consult Gemini
            result = await self.gemini.consult_gemini(
                query=query,
                context=context,
                comparison_mode=comparison_mode,
                force_consult=force_consult
            )

            # Format the response
            return await self._format_gemini_response(result)

        @self.server.call_tool()
        async def gemini_status(arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Get Gemini integration status and statistics."""
            return await self._get_gemini_status()

        @self.server.call_tool()
        async def toggle_gemini_auto_consult(arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Toggle automatic Gemini consultation on uncertainty detection."""
            enable = arguments.get('enable', None)

            if enable is None:
                # Toggle current state
                self.gemini.auto_consult = not self.gemini.auto_consult
            else:
                self.gemini.auto_consult = bool(enable)

            status = "enabled" if self.gemini.auto_consult else "disabled"
            return [types.TextContent(
                type="text",
                text=f"✅ Gemini auto-consultation is now {status}"
            )]

        @self.server.call_tool()
        async def clear_gemini_history(arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Clear Gemini conversation history."""
            result = self.gemini.clear_conversation_history()
            return [types.TextContent(
                type="text",
                text=f"✅ {result['message']}"
            )]

    async def _format_gemini_response(self, result: Dict[str, Any]) -> List[types.TextContent]:
        """Format Gemini consultation response for MCP output."""
        output_lines = []
        output_lines.append("🤖 Gemini Consultation Response")
        output_lines.append("=" * 40)
        output_lines.append("")

        if result['status'] == 'success':
            output_lines.append(f"✅ Consultation ID: {result['consultation_id']}")
            output_lines.append(f"⏱️  Execution time: {result['execution_time']:.2f}s")
            output_lines.append("")

            # Display the raw response (simplified format)
            response = result.get('response', '')
            if response:
                output_lines.append("📄 Response:")
                output_lines.append(response)

        elif result['status'] == 'disabled':
            output_lines.append("ℹ️  Gemini consultation is currently disabled")
            output_lines.append("💡 Enable with: toggle_gemini_auto_consult")

        elif result['status'] == 'timeout':
            output_lines.append(f"❌ {result['error']}")
            output_lines.append("💡 Try increasing the timeout or simplifying the query")

        else:  # error
            output_lines.append(f"❌ Error: {result.get('error', 'Unknown error')}")
            output_lines.append("")
            output_lines.append("💡 Troubleshooting:")
            output_lines.append("  1. Check if Gemini CLI is installed and in PATH")
            output_lines.append("  2. Verify Gemini CLI authentication")
            output_lines.append("  3. Check the logs for more details")

        return [types.TextContent(type="text", text="\n".join(output_lines))]

    async def _get_gemini_status(self) -> List[types.TextContent]:
        """Get Gemini integration status and statistics."""
        output_lines = []
        output_lines.append("🤖 Gemini Integration Status")
        output_lines.append("=" * 40)
        output_lines.append("")

        # Configuration status
        output_lines.append("⚙️  Configuration:")
        output_lines.append(f"  • Enabled: {'✅ Yes' if self.gemini.enabled else '❌ No'}")
        output_lines.append(f"  • Auto-consult: {'✅ Yes' if self.gemini.auto_consult else '❌ No'}")
        output_lines.append(f"  • CLI command: {self.gemini.cli_command}")
        output_lines.append(f"  • Timeout: {self.gemini.timeout}s")
        output_lines.append(f"  • Rate limit: {self.gemini.rate_limit_delay}s")
        output_lines.append("")

        # Check if Gemini CLI is available
        try:
            # Test with a simple prompt rather than --version (which may not be supported)
            check_process = await asyncio.create_subprocess_exec(
                self.gemini.cli_command, "-p", "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(check_process.communicate(), timeout=10)

            if check_process.returncode == 0:
                output_lines.append("✅ Gemini CLI is available and working")
                # Try to get version info from help or other means
                try:
                    help_process = await asyncio.create_subprocess_exec(
                        self.gemini.cli_command, "--help",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    help_stdout, _ = await help_process.communicate()
                    help_text = help_stdout.decode()
                    # Look for version in help output
                    if "version" in help_text.lower():
                        for line in help_text.split('\n'):
                            if 'version' in line.lower():
                                output_lines.append(f"  {line.strip()}")
                                break
                except:
                    pass
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                output_lines.append("❌ Gemini CLI found but not working properly")
                output_lines.append(f"  Command tested: {self.gemini.cli_command}")
                output_lines.append(f"  Error: {error_msg}")

                # Check for authentication issues
                if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                    output_lines.append("")
                    output_lines.append("🔑 Authentication required:")
                    output_lines.append("  1. Set GEMINI_API_KEY environment variable, or")
                    output_lines.append("  2. Run 'gemini' interactively to authenticate with Google")

        except asyncio.TimeoutError:
            output_lines.append("❌ Gemini CLI test timed out")
            output_lines.append("  This may indicate authentication is required")
        except FileNotFoundError:
            output_lines.append("❌ Gemini CLI not found in PATH")
            output_lines.append(f"  Expected command: {self.gemini.cli_command}")
            output_lines.append("")
            output_lines.append("📦 Installation:")
            output_lines.append("  npm install -g @google/gemini-cli")
            output_lines.append("  OR")
            output_lines.append("  npx @google/gemini-cli")
        except Exception as e:
            output_lines.append(f"❌ Error checking Gemini CLI: {str(e)}")

        output_lines.append("")

        # Consultation statistics
        stats = self.gemini.get_consultation_stats()
        output_lines.append("📊 Consultation Statistics:")
        output_lines.append(f"  • Total consultations: {stats.get('total_consultations', 0)}")

        completed = stats.get('completed_consultations', 0)
        output_lines.append(f"  • Completed: {completed}")

        if completed > 0:
            avg_time = stats.get('average_execution_time', 0)
            total_time = stats.get('total_execution_time', 0)
            output_lines.append(f"  • Average time: {avg_time:.2f}s")
            output_lines.append(f"  • Total time: {total_time:.2f}s")

        last_consultation = stats.get('last_consultation')
        if last_consultation:
            output_lines.append(f"  • Last consultation: {last_consultation}")

        output_lines.append("")
        output_lines.append("💡 Usage:")
        output_lines.append("  • Direct: Use 'consult_gemini' tool")
        output_lines.append("  • Auto: Enable auto-consult for uncertainty detection")
        output_lines.append("  • Toggle: Use 'toggle_gemini_auto_consult' tool")

        return [types.TextContent(type="text", text="\n".join(output_lines))]

    def detect_response_uncertainty(self, response: str) -> Tuple[bool, List[str]]:
        """
        Detect uncertainty in a response for potential auto-consultation.
        This is a wrapper around the GeminiIntegration's detection.
        """
        return self.gemini.detect_uncertainty(response)

    async def maybe_consult_gemini(self, response: str, context: str = "") -> Optional[Dict[str, Any]]:
        """
        Check if response contains uncertainty and consult Gemini if needed.

        Args:
            response: The response to check for uncertainty
            context: Additional context for the consultation

        Returns:
            Gemini consultation result if consulted, None otherwise
        """
        if not self.gemini.auto_consult or not self.gemini.enabled:
            return None

        has_uncertainty, patterns = self.detect_response_uncertainty(response)

        if has_uncertainty:
            # Extract the main question or topic from the response
            query = f"Please provide a second opinion on this analysis:\n\n{response}"

            # Add uncertainty patterns to context
            enhanced_context = f"{context}\n\nUncertainty detected in: {', '.join(patterns)}"

            result = await self.gemini.consult_gemini(
                query=query,
                context=enhanced_context,
                comparison_mode=True
            )

            return result

        return None

    def run(self):
        """Run the MCP server."""
        async def main():
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="gemini-mcp-server",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    ),
                )

        asyncio.run(main())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP Server with Gemini Integration")
    parser.add_argument(
        "--project-root",
        type=str,
        default=".",
        help="Path to the project root directory"
    )

    args = parser.parse_args()

    # Check if running in container - exit with instructions if true
    if os.path.exists("/.dockerenv") or os.environ.get("CONTAINER_ENV"):
        print("ERROR: Gemini MCP Server cannot run inside a container!", file=sys.stderr)
        print("The Gemini CLI requires Docker access and must run on the host system.", file=sys.stderr)
        print("Please launch this server directly on the host with:", file=sys.stderr)
        print("  python gemini_mcp_server_stdio.py", file=sys.stderr)
        sys.exit(1)

    server = MCPServer(args.project_root)
    server.run()
```
</details>

### Key Differences Between HTTP and stdio Versions:

| Feature | HTTP (FastAPI) | stdio (MCP Protocol) |
|---------|---------------|---------------------|
| **Communication** | Request/Response | Streaming, bidirectional |
| **Testing** | Easy with curl/requests | Requires MCP client |
| **Configuration** | Environment variables | .env + config files + args |
| **Features** | Basic consultation | Auto-consultation, status, toggle |
| **Error Handling** | Basic HTTP errors | Detailed diagnostics |
| **Deployment** | Standalone HTTP server | Integrated with MCP ecosystem |
| **Real-time Updates** | No | Yes (streaming) |

### Recommendation:
- Use **HTTP version** for: Development, testing, simple integrations
- Use **stdio version** for: Production, full MCP integration, advanced features

### Using the stdio Version:

The stdio version requires the MCP Python package and an MCP client:

```bash
# Install MCP package
pip install mcp
```

Here are the client options:

1. **MCP Hub** (if available):
   ```json
   {
     "mcpServers": {
       "gemini": {
         "command": "python",
         "args": ["path/to/gemini_mcp_server_stdio.py"],
         "env": {
           "GEMINI_API_KEY": "your-key-here"
         }
       }
     }
   }
   ```

2. **Direct stdio communication** (for testing):
   ```bash
   # Start the server
   python gemini_mcp_server_stdio.py --project-root /path/to/project

   # The server expects JSON-RPC messages on stdin and outputs on stdout
   ```

3. **Integration with other MCP clients**:
   - Claude Desktop
   - VS Code MCP extension
   - Custom MCP clients using the MCP SDK

## 2. Update mcp-server.py

**File: `mcp-server.py`**

Remove Gemini-related methods and tool registrations since they're now in the separate server.

**Lines to Remove: 82-139** (consult_gemini and clear_gemini_history methods)

**Lines to Update: Tool registry**
- Remove: `"consult_gemini": MCPTools.consult_gemini,`
- Remove: `"clear_gemini_history": MCPTools.clear_gemini_history,`

## 3. Add Test Scripts

### 3.1 Test Gemini MCP Server Script

**New File: `test-gemini-mcp-server.py`**

<details>
<summary>Full file content</summary>

```python
#!/usr/bin/env python3
"""Test script for Gemini MCP Server"""

import os
import sys

import requests


def test_gemini_mcp_server():
    """Test the Gemini MCP server endpoints"""
    # Use environment variable for port with default
    port = os.environ.get("GEMINI_MCP_PORT", "8006")
    base_url = f"http://localhost:{port}"

    print("Testing Gemini MCP Server...")
    print("-" * 50)

    # Test 1: Check if server is running
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Gemini MCP server on port {port}")
        print("   Please start it with: python tools/mcp/gemini_mcp_server.py")
        return False

    # Test 2: List available tools
    try:
        response = requests.get(f"{base_url}/mcp/tools")
        if response.status_code == 200:
            print("\n✅ Tool listing successful")
            tools = response.json()["tools"]
            for tool in tools:
                print(f"   - {tool['name']}: {tool['description']}")
        else:
            print(f"❌ Tool listing failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing tools: {e}")

    # Test 3: Test consult_gemini endpoint
    print("\n📝 Testing consult_gemini endpoint...")
    try:
        test_request = {
            "prompt": "What is the purpose of MCP (Model Context Protocol)?",
            "context": {"source": "test"},
            "max_retries": 1,
        }

        response = requests.post(
            f"{base_url}/tools/consult_gemini",
            json=test_request,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Gemini consultation successful")
            print(f"   Response preview: {result['response'][:200]}...")
            print(f"   Conversation ID: {result['conversation_id']}")
        else:
            print(f"❌ Gemini consultation failed: {response.status_code}")
            print(f"   Error: {response.json()}")
    except Exception as e:
        print(f"❌ Error consulting Gemini: {e}")

    # Test 4: Test clear_gemini_history endpoint
    print("\n🧹 Testing clear_gemini_history endpoint...")
    try:
        response = requests.post(f"{base_url}/tools/clear_gemini_history")

        if response.status_code == 200:
            result = response.json()
            print("✅ History clearing successful")
            print(f"   {result['message']}")
            print(f"   Cleared entries: {result['cleared_count']}")
        else:
            print(f"❌ History clearing failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error clearing history: {e}")

    print("\n" + "-" * 50)
    print("Test complete!")
    return True


if __name__ == "__main__":
    success = test_gemini_mcp_server()
    sys.exit(0 if success else 1)
```
</details>

### 3.2 Container Detection Test Script

**New File: `test-gemini-container-exit.sh`**

<details>
<summary>Full file content</summary>

```bash
#!/bin/bash
set -e
# Test that Gemini MCP server exits when run in a container

echo "Testing Gemini MCP server container detection..."

# Try to run in container - should exit with code 1
echo "Attempting to run Gemini MCP server in container..."
# Temporarily allow failure for this test
set +e
docker-compose run --rm gemini-mcp-server
EXIT_CODE=$?
set -e
if [ $EXIT_CODE -eq 1 ]; then
    echo "✅ SUCCESS: Gemini MCP server correctly exited with code 1 when run in container"
else
    echo "❌ FAILED: Expected exit code 1, got $EXIT_CODE"
    exit 1
fi

echo ""
echo "To run the Gemini MCP server properly, use:"
echo "  python tools/mcp/gemini_mcp_server.py"
```
</details>

## 4. Add Startup Helper Script

**New File: `start-gemini-mcp.sh`**

<details>
<summary>Full file content</summary>

```bash
#!/bin/bash
set -e

# Use environment variable for port with default
GEMINI_PORT=${GEMINI_MCP_PORT:-8006}

# Start Gemini MCP server in background
echo "Starting Gemini MCP server on port $GEMINI_PORT..."
nohup python3 tools/mcp/gemini_mcp_server.py > /tmp/gemini-mcp.log 2>&1 &
PID=$!
echo $PID > /tmp/gemini-mcp.pid
echo "Server started with PID $PID"
echo "Logs: /tmp/gemini-mcp.log"

echo "Waiting for server to become healthy..."
for i in {1..10}; do
    if curl -s http://localhost:$GEMINI_PORT/health | grep -q "healthy"; then
        echo "✅ Server is healthy."
        HEALTH_JSON=$(curl -s http://localhost:$GEMINI_PORT/health)
        if command -v jq &> /dev/null; then
            echo "$HEALTH_JSON" | jq
        else
            echo "$HEALTH_JSON"
        fi
        exit 0
    fi
    sleep 1
done

echo "❌ Server did not become healthy after 10 seconds."
exit 1
```
</details>

## 5. Update setup-gemini-integration.sh

**File: `setup-gemini-integration.sh`**

Add `set -e` at the beginning for better error handling:

**Line to Add: 2** (after shebang)
```bash
#!/bin/bash
set -e
```

## 6. Add MCP Configuration Example

**New File: `.mcp.json` (example snippet)**

<details>
<summary>Configuration for separate servers</summary>

```json
{
  "mcpServers": {
    "local-tools": {
      "name": "Local MCP Tools",
      "url": "http://localhost:8005",
      "tools": {
        "format_check": {},
        "lint": {},
        "create_manim_animation": {},
        "compile_latex": {}
      }
    },
    "gemini-tools": {
      "name": "Gemini MCP Server",
      "url": "http://localhost:8006",
      "note": "Must run on host system, not in container",
      "tools": {
        "consult_gemini": {
          "description": "Get AI assistance from Gemini",
          "parameters": {
            "prompt": {
              "type": "string",
              "description": "Technical question or code to review"
            },
            "context": {
              "type": "object",
              "description": "Additional context"
            },
            "max_retries": {
              "type": "integer",
              "description": "Maximum retry attempts",
              "default": 3
            }
          }
        },
        "clear_gemini_history": {
          "description": "Clear Gemini conversation history",
          "parameters": {}
        }
      }
    }
  }
}
```
</details>

## 7. Update gemini_integration.py

**File: `gemini_integration.py`**

The main change is in the consult_gemini method signature. In your gist, update:

**Line to Find: around line 85-90** (async def consult_gemini method)
```python
async def consult_gemini(
    self,
    query: str,
    context: str = "",
    comparison_mode: bool = True,
    force_consult: bool = False,
) -> Dict[str, Any]:
```

This matches our implementation and ensures compatibility with the separate server.

## 8. Port Configuration Improvement

### Centralized Port Management

To avoid hardcoded port mismatches, all scripts now respect the `GEMINI_MCP_PORT` environment variable:

**Changes Required:**

1. In `start-gemini-mcp.sh` - Add at the beginning:
   ```bash
   # Use environment variable for port with default
   GEMINI_PORT=${GEMINI_MCP_PORT:-8006}
   ```
   Then use `$GEMINI_PORT` instead of hardcoded 8006

2. In `test-gemini-mcp-server.py` - Add imports and port variable:
   ```python
   import os
   # Use environment variable for port with default
   port = os.environ.get("GEMINI_MCP_PORT", "8006")
   base_url = f"http://localhost:{port}"
   ```

This ensures consistency between the server (which already uses the environment variable) and the scripts that interact with it.

## Summary of Key Improvements

1. **Separation of Concerns**: Gemini functionality is now in its own MCP server
2. **Container Detection**: Automatic detection and helpful error messages
3. **Better Context Handling**: JSON formatting for context data
4. **Robust Shell Scripts**: Added `set -e` for error handling
5. **Comprehensive Testing**: Test scripts for server and container detection
6. **Port Separation**: Main MCP on 8005, Gemini MCP on 8006
7. **Enhanced Security**: Server binds to `127.0.0.1` by default instead of `0.0.0.0` to prevent network exposure
8. **Improved Reliability**: Startup script uses polling mechanism instead of fixed sleep to ensure server readiness
9. **Centralized Port Configuration**: All scripts respect `GEMINI_MCP_PORT` environment variable to avoid mismatches

## Security and Robustness Updates

### Security Fix (Critical)
The Gemini MCP server now defaults to binding only to localhost (`127.0.0.1`) instead of all network interfaces (`0.0.0.0`). This prevents the server from being accessible from other devices on the network, which is important since the server can execute shell commands via the Gemini CLI.

### Robustness Improvement
The `start-gemini-mcp.sh` script now uses a polling mechanism that:
- Attempts to connect to the health endpoint up to 10 times with 1-second intervals
- Provides clear feedback when the server is ready
- Exits with an error if the server doesn't become healthy within 10 seconds
- Eliminates race conditions that could occur with a fixed sleep duration

These updates will make your gist reflect the latest architectural improvements while maintaining the simplicity of the setup process and ensuring secure operation.
