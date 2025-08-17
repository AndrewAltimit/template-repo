"""Shared test utilities for Blender MCP server tests."""

import asyncio
from typing import Any, Dict, Optional

import httpx


class TestClient:
    """Test client wrapper for Blender MCP server testing."""

    def __init__(self, base_url: str = "http://localhost:8017"):
        """Initialize test client.

        Args:
            base_url: Base URL of the MCP server
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via HTTP API.

        Args:
            tool_name: Name of the tool to call
            params: Tool parameters

        Returns:
            Tool execution result
        """
        try:
            response = await self.client.post(f"{self.base_url}/mcp/execute", json={"tool": tool_name, "arguments": params})

            if response.status_code == 200:
                result = response.json()
                if result is None:
                    return {"error": "Empty response from server"}
                return dict(result.get("result", result))
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": str(e)}

    async def wait_for_job(self, job_id: str, timeout: int = 30, poll_interval: float = 0.5) -> Dict[str, Any]:
        """Wait for a job to complete.

        Args:
            job_id: Job ID to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks

        Returns:
            Final job result
        """
        elapsed: float = 0
        while elapsed < timeout:
            result = await self.call_tool("get_job_status", {"job_id": job_id})

            if "error" in result:
                return result

            status = result.get("status", "unknown")
            if status in ["completed", "failed"]:
                if status == "completed":
                    # Get the final result
                    return await self.call_tool("get_job_result", {"job_id": job_id})
                else:
                    return result

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {"error": f"Job {job_id} timed out after {timeout} seconds"}

    async def create_test_project(self, name: str = "test_project") -> Dict[str, Any]:
        """Create a test project with basic setup.

        Args:
            name: Project name

        Returns:
            Project creation result
        """
        result = await self.call_tool(
            "create_blender_project",
            {"name": name, "template": "basic_scene", "settings": {"engine": "EEVEE", "resolution": [1920, 1080], "fps": 24}},
        )

        if "job_id" in result:
            return await self.wait_for_job(result["job_id"])
        return result

    async def cleanup_project(self, project_path: str) -> None:
        """Clean up a test project.

        Args:
            project_path: Path to the project to clean up
        """
        # Note: Implement cleanup if needed
        pass

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()


def create_test_client(base_url: Optional[str] = None) -> TestClient:
    """Create a test client instance.

    Args:
        base_url: Optional base URL for the server

    Returns:
        TestClient instance
    """
    if base_url:
        return TestClient(base_url)
    return TestClient()


async def wait_for_server(base_url: str = "http://localhost:8017", timeout: int = 30) -> bool:
    """Wait for server to be ready.

    Args:
        base_url: Server base URL
        timeout: Maximum time to wait

    Returns:
        True if server is ready, False if timeout
    """
    client = httpx.AsyncClient()
    elapsed = 0

    try:
        while elapsed < timeout:
            try:
                response = await client.get(f"{base_url}/health")
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass

            await asyncio.sleep(1)
            elapsed += 1

        return False
    finally:
        await client.aclose()


class MockBlenderExecutor:
    """Mock Blender executor for unit testing."""

    def __init__(self):
        """Initialize mock executor."""
        self.executed_commands = []
        self.return_values = {}

    def set_return_value(self, command: str, value: Any):
        """Set a return value for a specific command.

        Args:
            command: Command pattern to match
            value: Value to return
        """
        self.return_values[command] = value

    async def execute(self, script: str, *args, **kwargs) -> Dict[str, Any]:
        """Mock execute method.

        Args:
            script: Script to execute
            *args: Additional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Mock result
        """
        self.executed_commands.append(script)

        # Check if we have a configured return value
        for pattern, value in self.return_values.items():
            if pattern in script:
                return dict(value)

        # Default success response
        return {"success": True, "message": "Mock execution completed"}

    def assert_command_executed(self, pattern: str) -> bool:
        """Assert a command pattern was executed.

        Args:
            pattern: Pattern to search for in executed commands

        Returns:
            True if pattern found
        """
        return any(pattern in cmd for cmd in self.executed_commands)


# Common test data fixtures
TEST_PROJECT_SETTINGS = {"engine": "CYCLES", "resolution": [1920, 1080], "fps": 24, "samples": 128}

TEST_MATERIAL_SETTINGS = {"base_color": [0.5, 0.5, 0.8, 1.0], "metallic": 0.0, "roughness": 0.5, "emission_strength": 0}

TEST_CAMERA_SETTINGS = {"location": [7, -7, 5], "rotation": [60, 0, 45], "focal_length": 50, "sensor_width": 36}
