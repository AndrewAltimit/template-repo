"""Meme Generator MCP Server - Create memes from templates with text overlays"""

import os
import tempfile
from typing import Any, Dict, Optional

from ..core.base_server import BaseMCPServer
from ..core.utils import ensure_directory, setup_logging
from .tools import (
    generate_meme,
    get_meme_template_info,
    initialize_generator,
    list_meme_templates,
    test_fake_meme,
    test_minimal,
)

WEBP_QUALITY_HIGH = 75
WEBP_QUALITY_LOW = 50
JPEG_QUALITY_HIGH = 85
JPEG_QUALITY_LOW = 70
MAX_IMAGE_SIZE_WEBP = 25000  # 25KB for WebP
MAX_IMAGE_SIZE_JPEG = 100000
MAX_IMAGE_SIZE_PNG = 200000


class MemeGeneratorMCPServer(BaseMCPServer):
    """MCP Server for meme generation with templates and visual feedback"""

    def __init__(
        self,
        templates_dir: Optional[str] = None,
        output_dir: str = "/app/output",
        stdio_mode: bool = False,
    ):
        super().__init__(
            name="Meme Generator MCP Server",
            version="1.0.0",
            port=8016,
        )
        # Disable logging in STDIO mode to prevent output pollution
        if stdio_mode:
            import logging

            logging.getLogger().setLevel(logging.CRITICAL)
            self.logger = logging.getLogger("MemeGeneratorMCP")
        else:
            self.logger = setup_logging("MemeGeneratorMCP")

        if templates_dir is None:
            templates_dir = os.path.join(os.path.dirname(__file__), "templates")

        self.templates_dir = templates_dir
        self.output_dir = os.environ.get("MCP_OUTPUT_DIR", output_dir)
        self.logger.info(f"Using templates directory: {self.templates_dir}")
        self.logger.info(f"Using output directory: {self.output_dir}")

        try:
            self.meme_output_dir = ensure_directory(os.path.join(self.output_dir, "memes"))
            self.logger.info("Successfully created output directory")
        except Exception as e:
            self.logger.error(f"Failed to create output directory: {e}")
            temp_dir = tempfile.mkdtemp(prefix="mcp_meme_")
            self.output_dir = temp_dir
            self.meme_output_dir = ensure_directory(os.path.join(temp_dir, "memes"))
            self.logger.warning(f"Using fallback temp directory: {temp_dir}")

        initialize_generator(self.templates_dir, self.meme_output_dir)

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available meme generation tools"""
        return {
            "generate_meme": {
                "description": "Generate a meme from a template with text overlays",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "description": "Template ID (e.g., 'ol_reliable')",
                        },
                        "texts": {
                            "type": "object",
                            "description": "Text for each area (e.g., {'top': 'When...', 'bottom': 'Ol Reliable'})",
                            "additionalProperties": {"type": "string"},
                        },
                        "font_size_override": {
                            "type": "object",
                            "description": "Override font sizes for specific areas",
                            "additionalProperties": {"type": "integer"},
                        },
                        "auto_resize": {
                            "type": "boolean",
                            "default": True,
                            "description": "Automatically resize font to fit text",
                        },
                        "upload": {
                            "type": "boolean",
                            "default": True,
                            "description": "Upload meme to get shareable URL (uses 0x0.st)",
                        },
                    },
                    "required": ["template", "texts"],
                },
            },
            "list_meme_templates": {
                "description": "List all available meme templates",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "get_meme_template_info": {
                "description": "Get detailed information about a specific meme template",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template_id": {
                            "type": "string",
                            "description": "Template ID to get info for",
                        },
                    },
                    "required": ["template_id"],
                },
            },
            "test_minimal": {
                "description": "Minimal test tool that returns a tiny response",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "test_fake_meme": {
                "description": "Test meme generation without actually creating an image",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "description": "Template ID",
                        },
                        "texts": {
                            "type": "object",
                            "description": "Text for each area",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    "required": ["template", "texts"],
                },
            },
        }

    async def generate_meme(
        self,
        template: str,
        texts: Dict[str, str],
        font_size_override: Optional[Dict[str, int]] = None,
        auto_resize: bool = True,
        upload: bool = True,
    ) -> Dict[str, Any]:
        """Generate a meme with visual feedback and optional upload

        Args:
            template: Template ID
            texts: Text for each area
            font_size_override: Custom font sizes
            auto_resize: Auto-adjust font size
            upload: Upload to get shareable URL

        Returns:
            Dictionary with meme data, visual feedback, and optional share URL
        """
        try:
            # Generate meme (now returns compact WebP with visual feedback and optional upload)
            result = await generate_meme(template, texts, font_size_override, auto_resize, upload)

            # The tool now returns a compact response with visual feedback included
            return dict(result)

        except Exception as e:
            self.logger.error(f"Meme generation error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def list_meme_templates(self) -> Dict[str, Any]:
        """List available meme templates

        Returns:
            Dictionary with list of templates
        """
        try:
            result: Dict[str, Any] = await list_meme_templates()
            return result
        except Exception as e:
            self.logger.error(f"Error listing templates: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_meme_template_info(self, template_id: str) -> Dict[str, Any]:
        """Get detailed template information

        Args:
            template_id: Template to get info for

        Returns:
            Dictionary with template configuration
        """
        try:
            result: Dict[str, Any] = await get_meme_template_info(template_id)
            return result
        except Exception as e:
            self.logger.error(f"Error getting template info: {str(e)}")
            return {"success": False, "error": str(e)}

    async def test_minimal(self) -> Dict[str, Any]:
        """Minimal test tool

        Returns:
            Tiny test response
        """
        result: Dict[str, Any] = await test_minimal()
        return result

    async def test_fake_meme(self, template: str, texts: Dict[str, str]) -> Dict[str, Any]:
        """Test fake meme generation

        Args:
            template: Template ID
            texts: Text for each area

        Returns:
            Fake meme response
        """
        result: Dict[str, Any] = await test_fake_meme(template, texts)
        return result


def main():
    """Run the Meme Generator MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="Meme Generator MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8016,
        help="Port for HTTP mode",
    )
    parser.add_argument(
        "--templates",
        type=str,
        help="Path to templates directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/app/output",
        help="Output directory for generated memes",
    )

    args = parser.parse_args()

    # Pass stdio_mode flag to disable logging in STDIO mode
    stdio_mode = args.mode == "stdio"
    server = MemeGeneratorMCPServer(templates_dir=args.templates, output_dir=args.output, stdio_mode=stdio_mode)

    if args.mode == "http":
        server.run_http()
    else:
        import asyncio

        asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
