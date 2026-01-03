"""Tests for Meme Generator MCP Server.

Tests tool registration and MemeGenerator class functionality.
"""

import sys
from pathlib import Path

# Insert source directory at beginning of path to import from source, not site-packages
_source_dir = Path(__file__).parent.parent
if str(_source_dir) not in sys.path:
    sys.path.insert(0, str(_source_dir))

# Remove any cached imports from site-packages
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("mcp_meme_generator"):
        del sys.modules[mod_name]


import pytest
from unittest.mock import MagicMock, patch
import tempfile
import os
import json


class TestMemeGeneratorToolsRegistry:
    """Test tools registry structure."""

    def test_tools_import(self):
        """Test tools registry can be imported."""
        from mcp_meme_generator.tools import TOOLS

        assert isinstance(TOOLS, dict)

    def test_tools_registry_has_expected_tools(self):
        """Test tools registry contains expected tools."""
        from mcp_meme_generator.tools import TOOLS

        expected_tools = [
            "generate_meme",
            "list_meme_templates",
            "get_meme_template_info",
            "test_minimal",
            "test_fake_meme",
        ]
        for tool in expected_tools:
            assert tool in TOOLS, f"Missing tool: {tool}"


class TestMemeGeneratorClass:
    """Test MemeGenerator class functionality."""

    def test_meme_generator_import(self):
        """Test MemeGenerator class can be imported."""
        from mcp_meme_generator.tools import MemeGenerator

        assert MemeGenerator is not None

    def test_meme_generator_init(self):
        """Test MemeGenerator initialization."""
        from mcp_meme_generator.tools import MemeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MemeGenerator(tmpdir)
            assert generator.templates_dir == tmpdir
            assert generator.templates == {}  # No templates in empty dir

    def test_meme_generator_get_font(self):
        """Test font loading."""
        from mcp_meme_generator.tools import MemeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MemeGenerator(tmpdir)
            font = generator._get_font(24)
            assert font is not None

    def test_meme_generator_wrap_text(self):
        """Test text wrapping functionality."""
        from mcp_meme_generator.tools import MemeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MemeGenerator(tmpdir)
            font = generator._get_font(24)

            # Short text should not wrap
            lines = generator._wrap_text("Hello", font, 500)
            assert len(lines) == 1
            assert lines[0] == "Hello"

            # Long text should wrap
            long_text = "This is a very long sentence that should wrap to multiple lines"
            lines = generator._wrap_text(long_text, font, 100)
            assert len(lines) > 1

    def test_meme_generator_list_templates_empty(self):
        """Test listing templates from empty directory."""
        from mcp_meme_generator.tools import MemeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MemeGenerator(tmpdir)
            result = generator.list_templates()
            assert result["success"] is True
            assert result["templates"] == []

    def test_meme_generator_get_template_not_found(self):
        """Test getting non-existent template."""
        from mcp_meme_generator.tools import MemeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MemeGenerator(tmpdir)
            result = generator.get_template_info("nonexistent")
            assert result["success"] is False
            assert "not found" in result["error"]


class TestMemeGeneratorWithTemplates:
    """Test MemeGenerator with mock templates."""

    @pytest.fixture
    def mock_template_dir(self):
        """Create a temporary directory with mock template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config directory
            config_dir = os.path.join(tmpdir, "config")
            os.makedirs(config_dir)

            # Create mock template config
            template_config = {
                "name": "Test Template",
                "description": "A test template for unit testing",
                "template_file": "test_template.png",
                "text_areas": [
                    {
                        "id": "top",
                        "position": {"x": 200, "y": 50},
                        "width": 350,
                        "height": 100,
                        "default_font_size": 36,
                        "min_font_size": 12,
                        "max_font_size": 72,
                        "text_color": "white",
                        "stroke_color": "black",
                        "stroke_width": 2,
                        "text_align": "center",
                    },
                    {
                        "id": "bottom",
                        "position": {"x": 200, "y": 350},
                        "width": 350,
                        "height": 100,
                        "default_font_size": 36,
                        "min_font_size": 12,
                        "max_font_size": 72,
                        "text_color": "white",
                        "stroke_color": "black",
                        "stroke_width": 2,
                        "text_align": "center",
                    },
                ],
            }

            config_path = os.path.join(config_dir, "test_template.json")
            with open(config_path, "w") as f:
                json.dump(template_config, f)

            # Create mock template image (solid color PNG)
            from PIL import Image

            img = Image.new("RGB", (400, 400), color=(100, 100, 100))
            img.save(os.path.join(tmpdir, "test_template.png"))

            yield tmpdir

    def test_load_templates(self, mock_template_dir):
        """Test loading templates from directory."""
        from mcp_meme_generator.tools import MemeGenerator

        generator = MemeGenerator(mock_template_dir)
        assert "test_template" in generator.templates
        assert generator.templates["test_template"]["name"] == "Test Template"

    def test_list_templates(self, mock_template_dir):
        """Test listing loaded templates."""
        from mcp_meme_generator.tools import MemeGenerator

        generator = MemeGenerator(mock_template_dir)
        result = generator.list_templates()

        assert result["success"] is True
        assert len(result["templates"]) == 1
        assert result["templates"][0]["id"] == "test_template"
        assert result["templates"][0]["name"] == "Test Template"

    def test_get_template_info(self, mock_template_dir):
        """Test getting template info."""
        from mcp_meme_generator.tools import MemeGenerator

        generator = MemeGenerator(mock_template_dir)
        result = generator.get_template_info("test_template")

        assert result["success"] is True
        assert result["template"]["name"] == "Test Template"
        assert len(result["template"]["text_areas"]) == 2

    def test_generate_meme(self, mock_template_dir):
        """Test generating a meme."""
        from mcp_meme_generator.tools import MemeGenerator

        generator = MemeGenerator(mock_template_dir)
        result = generator.generate_meme(
            template_id="test_template",
            texts={"top": "Hello", "bottom": "World"},
        )

        assert result["success"] is True
        assert "image_data" in result
        assert result["template_used"] == "test_template"
        assert "text_positions" in result

    def test_generate_meme_auto_resize(self, mock_template_dir):
        """Test meme generation with auto-resize."""
        from mcp_meme_generator.tools import MemeGenerator

        generator = MemeGenerator(mock_template_dir)

        # Long text should trigger auto-resize
        long_text = "This is a very long text that should be auto-resized to fit"
        result = generator.generate_meme(
            template_id="test_template",
            texts={"top": long_text},
            auto_resize=True,
        )

        assert result["success"] is True

    def test_generate_meme_thumbnail(self, mock_template_dir):
        """Test generating thumbnail only."""
        from mcp_meme_generator.tools import MemeGenerator

        generator = MemeGenerator(mock_template_dir)
        result = generator.generate_meme(
            template_id="test_template",
            texts={"top": "Hello"},
            thumbnail_only=True,
        )

        assert result["success"] is True
        assert result["format"] == "webp"
        assert result["thumbnail"] is True

    def test_generate_meme_template_not_found(self, mock_template_dir):
        """Test generating meme with non-existent template."""
        from mcp_meme_generator.tools import MemeGenerator

        generator = MemeGenerator(mock_template_dir)
        result = generator.generate_meme(
            template_id="nonexistent",
            texts={"top": "Hello"},
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_create_thumbnail_from_image(self, mock_template_dir):
        """Test creating thumbnail from PIL image."""
        from mcp_meme_generator.tools import MemeGenerator
        from PIL import Image

        generator = MemeGenerator(mock_template_dir)
        img = Image.new("RGB", (800, 600), color=(200, 100, 100))
        result = generator.create_thumbnail_from_image(img, max_width=150)

        assert result["success"] is True
        assert result["format"] == "webp"
        assert "image_data" in result


@pytest.mark.asyncio
class TestMemeGeneratorAsync:
    """Test async meme generation functions."""

    async def test_list_meme_templates_tool(self):
        """Test list_meme_templates async tool."""
        from mcp_meme_generator.tools import list_meme_templates, initialize_generator

        with tempfile.TemporaryDirectory() as tmpdir:
            initialize_generator(tmpdir, tmpdir)
            result = await list_meme_templates()

            assert result["success"] is True
            assert "templates" in result

    async def test_get_meme_template_info_tool(self):
        """Test get_meme_template_info async tool."""
        from mcp_meme_generator.tools import get_meme_template_info, initialize_generator

        with tempfile.TemporaryDirectory() as tmpdir:
            initialize_generator(tmpdir, tmpdir)
            result = await get_meme_template_info("nonexistent")

            assert result["success"] is False

    async def test_test_minimal_tool(self):
        """Test test_minimal async tool."""
        from mcp_meme_generator.tools import test_minimal, initialize_generator

        with tempfile.TemporaryDirectory() as tmpdir:
            initialize_generator(tmpdir, tmpdir)
            result = await test_minimal()

            assert result["success"] is True
            assert "message" in result

    async def test_test_fake_meme_tool(self):
        """Test test_fake_meme async tool."""
        from mcp_meme_generator.tools import test_fake_meme

        result = await test_fake_meme(
            template="test",
            texts={"top": "Hello"},
        )

        assert result["success"] is True
        assert "output_path" in result


class TestDrawTextWithStroke:
    """Test text drawing with stroke effect."""

    def test_draw_text_with_stroke(self):
        """Test drawing text with stroke effect."""
        from mcp_meme_generator.tools import MemeGenerator
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MemeGenerator(tmpdir)
            img = Image.new("RGB", (200, 100), color=(128, 128, 128))
            draw = ImageDraw.Draw(img)
            font = generator._get_font(24)

            # Should not raise
            generator._draw_text_with_stroke(
                draw,
                (50, 50),
                "Test",
                font,
                text_color="white",
                stroke_color="black",
                stroke_width=2,
            )

            # Verify image was modified (not all gray)
            pixels = list(img.getdata())
            unique_pixels = set(pixels)
            assert len(unique_pixels) > 1  # Should have text pixels


class TestMemeServerImport:
    """Test server can be imported."""

    def test_server_import(self):
        """Test server module can be imported."""
        from mcp_meme_generator.server import MemeGeneratorMCPServer

        assert MemeGeneratorMCPServer is not None

    def test_server_init(self):
        """Test server initialization."""
        from mcp_meme_generator.server import MemeGeneratorMCPServer

        with tempfile.TemporaryDirectory() as tmpdir:
            server = MemeGeneratorMCPServer(output_dir=tmpdir, stdio_mode=True)
            assert server.name == "Meme Generator MCP Server"
            assert server.version == "1.0.0"
            assert server.port == 8016

    def test_server_get_tools(self):
        """Test get_tools returns valid schema."""
        from mcp_meme_generator.server import MemeGeneratorMCPServer

        with tempfile.TemporaryDirectory() as tmpdir:
            server = MemeGeneratorMCPServer(output_dir=tmpdir, stdio_mode=True)
            tools = server.get_tools()

            assert isinstance(tools, dict)
            assert "generate_meme" in tools
            assert "list_meme_templates" in tools
            assert "get_meme_template_info" in tools
