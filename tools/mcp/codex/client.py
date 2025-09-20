"""Client for Codex MCP Server"""

from typing import Any, Dict, Optional

from ..core.client import MCPClient


class CodexClient:
    """Client for interacting with Codex MCP Server"""

    def __init__(self, port: int = 8021):
        self.client = MCPClient(base_url=f"http://localhost:{port}")

    def consult_codex(
        self,
        query: str,
        context: str = "",
        mode: str = "quick",
        comparison_mode: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Consult Codex for code generation or assistance"""
        return self.client.execute_tool(
            "consult_codex",
            {
                "query": query,
                "context": context,
                "mode": mode,
                "comparison_mode": comparison_mode,
                "force": force,
            },
        )

    def clear_history(self) -> Dict[str, Any]:
        """Clear Codex conversation history"""
        return self.client.execute_tool("clear_codex_history", {})

    def get_status(self) -> Dict[str, Any]:
        """Get Codex integration status"""
        return self.client.execute_tool("codex_status", {})

    def toggle_auto_consult(self, enable: Optional[bool] = None) -> Dict[str, Any]:
        """Toggle automatic Codex consultation"""
        params: Dict[str, Any] = {}
        if enable is not None:
            params["enable"] = enable
        return self.client.execute_tool("toggle_codex_auto_consult", params)


def main():
    """Example usage of Codex client"""
    client = CodexClient()

    # Get status
    print("Getting Codex status...")
    status = client.get_status()
    print(f"Status: {status}")

    # Example consultation
    print("\nConsulting Codex...")
    result = client.consult_codex(
        query="Write a Python function to calculate fibonacci numbers",
        mode="generate",
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
