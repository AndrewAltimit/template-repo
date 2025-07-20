#!/usr/bin/env python3
"""Test script for Content Creation MCP Server"""

import asyncio
import json  # noqa: F401
import sys
from pathlib import Path  # noqa: F401

import httpx


async def test_content_creation_server(base_url: str = "http://localhost:8011"):
    """Test Content Creation MCP Server endpoints"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Testing Content Creation MCP Server...")
        print(f"Base URL: {base_url}\n")

        # Test health endpoint
        try:
            response = await client.get(f"{base_url}/health")
            print(f"✓ Health check: {response.json()}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return

        # Test listing tools
        try:
            response = await client.get(f"{base_url}/mcp/tools")
            tools = response.json()
            print(f"\n✓ Available tools: {len(tools['tools'])} tools")
            for tool in tools["tools"]:
                print(f"  - {tool['name']}: {tool['description']}")
        except Exception as e:
            print(f"✗ Failed to list tools: {e}")

        # Test LaTeX compilation
        print("\n--- Testing LaTeX compilation ---")
        latex_content = """
\\section{Test Document}
This is a test document created by the MCP server.

\\begin{equation}
E = mc^2
\\end{equation}

\\begin{itemize}
\\item First item
\\item Second item
\\item Third item
\\end{itemize}
"""

        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "compile_latex",
                    "arguments": {
                        "content": latex_content,
                        "format": "pdf",
                        "template": "article",
                    },
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ LaTeX compilation completed")
                print(f"  Output: {result['result']['output_path']}")
                print(f"  Format: {result['result']['format']}")
            else:
                print(f"✗ LaTeX compilation failed: {result.get('error', result['result'].get('error'))}")
        except Exception as e:
            print(f"✗ LaTeX compilation error: {e}")

        # Test TikZ rendering
        print("\n--- Testing TikZ rendering ---")
        tikz_code = """
\\begin{tikzpicture}
  \\node[circle,draw] (A) at (0,0) {A};
  \\node[circle,draw] (B) at (2,0) {B};
  \\draw[->] (A) -- (B);
\\end{tikzpicture}
"""

        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "render_tikz",
                    "arguments": {"tikz_code": tikz_code, "output_format": "pdf"},
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ TikZ rendering completed")
                print(f"  Output: {result['result']['output_path']}")
            else:
                print(f"✗ TikZ rendering failed: {result.get('error', result['result'].get('error'))}")
        except Exception as e:
            print(f"✗ TikZ rendering error: {e}")

        # Test Manim animation (simple example)
        print("\n--- Testing Manim animation ---")
        manim_script = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # Create a circle
        circle = Circle(radius=1, color=BLUE)

        # Create text
        text = Text("MCP Test", font_size=36)
        text.next_to(circle, DOWN)

        # Animate
        self.play(Create(circle))
        self.play(Write(text))
        self.wait(1)
"""

        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "create_manim_animation",
                    "arguments": {
                        "script": manim_script,
                        "output_format": "mp4",
                        "quality": "low",
                        "preview": True,
                    },
                },
                timeout=60.0,  # Manim can take time
            )
            result = response.json()
            if result["success"]:
                print("✓ Manim animation created")
                print(f"  Output: {result['result']['output_path']}")
                print(f"  Format: {result['result']['format']}")
                print(f"  Preview: {result['result']['preview']}")
            else:
                print(f"✗ Manim animation failed: {result.get('error', result['result'].get('error'))}")
        except Exception as e:
            print(f"✗ Manim animation error: {e}")

        # Test error handling
        print("\n--- Testing error handling ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "compile_latex",
                    "arguments": {"content": "\\invalid{latex}", "format": "pdf"},
                },
            )
            result = response.json()
            if not result["success"] or "error" in result["result"]:
                print("✓ Error handling works correctly")
                print(f"  Error: {result.get('error', result['result'].get('error'))[:100]}...")
            else:
                print("✗ Expected error for invalid LaTeX")
        except Exception as e:
            print(f"✗ Error handling test failed: {e}")

        print("\n✅ Content Creation MCP Server tests completed!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8011"

    asyncio.run(test_content_creation_server(base_url))
