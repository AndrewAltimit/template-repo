"""Meme generation tools for MCP"""

import base64
import io
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool"""

    def decorator(func):
        TOOLS[name] = func
        return func

    return decorator


class MemeGenerator:
    """Handles meme generation with text overlays"""

    def __init__(self, templates_dir: str):
        self.templates_dir = templates_dir
        self.config_dir = os.path.join(templates_dir, "config")
        self.default_font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all template configurations"""
        self.templates = {}
        if os.path.exists(self.config_dir):
            for filename in os.listdir(self.config_dir):
                if filename.endswith(".json") and filename != "template_schema.json":
                    config_path = os.path.join(self.config_dir, filename)
                    with open(config_path, "r") as f:
                        config = json.load(f)
                        template_id = filename.replace(".json", "")
                        self.templates[template_id] = config

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font with specified size"""
        try:
            return ImageFont.truetype(self.default_font_path, size)
        except Exception:
            return ImageFont.load_default()

    def _draw_text_with_stroke(
        self,
        draw: ImageDraw.Draw,
        position: Tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        text_color: str = "white",
        stroke_color: str = "black",
        stroke_width: int = 2,
    ) -> None:
        """Draw text with stroke/outline effect"""
        x, y = position
        for adj_x in range(-stroke_width, stroke_width + 1):
            for adj_y in range(-stroke_width, stroke_width + 1):
                if adj_x != 0 or adj_y != 0:
                    draw.text((x + adj_x, y + adj_y), text, font=font, fill=stroke_color)
        draw.text(position, text, font=font, fill=text_color)

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Wrap text to fit within max_width"""
        words = text.split()
        lines = []
        current_line: List[str] = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def _calculate_text_position(
        self,
        lines: List[str],
        font: ImageFont.FreeTypeFont,
        area_config: Dict[str, Any],
    ) -> List[Tuple[Tuple[int, int], str]]:
        """Calculate position for each line of text"""
        positions = []
        total_height = len(lines) * font.size
        area_center_x = area_config["position"]["x"]
        area_center_y = area_config["position"]["y"]
        align = area_config.get("text_align", "center")

        start_y = area_center_y - total_height // 2

        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            text_width = bbox[2] - bbox[0]

            if align == "center":
                x = area_center_x - text_width // 2
            elif align == "left":
                x = area_center_x - area_config["width"] // 2
            else:
                x = area_center_x + area_config["width"] // 2 - text_width

            y = start_y + i * font.size
            positions.append(((x, y), line))

        return positions

    def _auto_adjust_font_size(
        self,
        text: str,
        area_config: Dict[str, Any],
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> Tuple[ImageFont.FreeTypeFont, List[str]]:
        """Auto-adjust font size to fit text in area"""
        default_size = area_config["default_font_size"]
        min_size = min_size or area_config.get("min_font_size", 12)
        max_size = max_size or area_config.get("max_font_size", default_size * 2)

        for size in range(max_size, min_size - 1, -2):
            font = self._get_font(size)
            lines = self._wrap_text(text, font, area_config["width"])
            total_height = len(lines) * size

            if total_height <= area_config["height"]:
                return font, lines

        font = self._get_font(min_size)
        lines = self._wrap_text(text, font, area_config["width"])
        return font, lines

    def generate_meme(
        self,
        template_id: str,
        texts: Dict[str, str],
        font_size_override: Optional[Dict[str, int]] = None,
        auto_resize: bool = True,
        thumbnail_only: bool = False,
        return_pil_image: bool = False,
    ) -> Dict[str, Any]:
        """Generate a meme from template with text overlays

        Args:
            template_id: ID of the template to use
            texts: Dictionary of text for each area
            font_size_override: Optional custom font sizes
            auto_resize: Whether to auto-resize text
            thumbnail_only: Generate only a thumbnail
            return_pil_image: Return PIL Image object in addition to base64

        Returns:
            Dict with success status, image data, and optional PIL Image
        """
        if template_id not in self.templates:
            return {"success": False, "error": f"Template '{template_id}' not found"}

        template_config = self.templates[template_id]
        template_path = os.path.join(self.templates_dir, template_config["template_file"])

        if not os.path.exists(template_path):
            return {
                "success": False,
                "error": f"Template image not found: {template_path}",
            }

        try:
            img = Image.open(template_path).convert("RGB")
            draw = ImageDraw.Draw(img)

            text_positions = {}

            for area in template_config["text_areas"]:
                area_id = area["id"]
                if area_id not in texts:
                    continue

                text = texts[area_id]
                if not text:
                    continue

                if font_size_override and area_id in font_size_override:
                    font_size = font_size_override[area_id]
                    font = self._get_font(font_size)
                    lines = self._wrap_text(text, font, area["width"])
                elif auto_resize:
                    font, lines = self._auto_adjust_font_size(text, area)
                else:
                    font = self._get_font(area["default_font_size"])
                    lines = self._wrap_text(text, font, area["width"])

                positions = self._calculate_text_position(lines, font, area)
                text_positions[area_id] = {
                    "lines": lines,
                    "font_size": font.size,
                    "positions": [(pos[0], pos[1]) for pos, _ in positions],
                }

                for position, line in positions:
                    self._draw_text_with_stroke(
                        draw,
                        position,
                        line,
                        font,
                        text_color=area.get("text_color", "white"),
                        stroke_color=area.get("stroke_color", "black"),
                        stroke_width=area.get("stroke_width", 2),
                    )

            # Generate image with base64 encoding
            if thumbnail_only:
                max_width = 150  # Very small thumbnail
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                # Save as WebP with aggressive compression
                buffer = io.BytesIO()
                img.save(buffer, format="WEBP", quality=30, method=6)
                img_data = buffer.getvalue()
                format_type = "webp"
            else:
                # Full size PNG
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", optimize=True)
                img_data = buffer.getvalue()
                format_type = "png"

            result = {
                "success": True,
                "image_data": base64.b64encode(img_data).decode("utf-8"),
                "format": format_type,
                "template_used": template_id,
                "text_positions": text_positions,
                "size_kb": len(img_data) / 1024,
                "thumbnail": thumbnail_only,
            }

            # Optionally return the PIL Image object for reuse
            if return_pil_image:
                result["pil_image"] = img

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_thumbnail_from_image(self, img: Image.Image, max_width: int = 150) -> Dict[str, Any]:
        """Create a thumbnail from an existing PIL Image

        Args:
            img: PIL Image object
            max_width: Maximum width for thumbnail

        Returns:
            Dict with thumbnail data in base64
        """
        try:
            # Create a copy to avoid modifying the original
            thumbnail = img.copy()

            # Resize if needed
            if thumbnail.width > max_width:
                ratio = max_width / thumbnail.width
                new_height = int(thumbnail.height * ratio)
                thumbnail = thumbnail.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Save as WebP with aggressive compression
            buffer = io.BytesIO()
            thumbnail.save(buffer, format="WEBP", quality=30, method=6)
            img_data = buffer.getvalue()

            return {
                "success": True,
                "image_data": base64.b64encode(img_data).decode("utf-8"),
                "format": "webp",
                "size_kb": len(img_data) / 1024,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_template_info(self, template_id: str) -> Dict[str, Any]:
        """Get information about a specific template"""
        if template_id not in self.templates:
            return {"success": False, "error": f"Template '{template_id}' not found"}

        return {"success": True, "template": self.templates[template_id]}

    def list_templates(self) -> Dict[str, Any]:
        """List all available templates"""
        template_list = []
        for template_id, config in self.templates.items():
            template_list.append(
                {
                    "id": template_id,
                    "name": config.get("name", template_id),
                    "description": config.get("description", ""),
                    "text_areas": [area["id"] for area in config.get("text_areas", [])],
                }
            )
        return {"success": True, "templates": template_list}


# Global instances
generator = None
output_directory = None


def initialize_generator(templates_dir: str, output_dir: Optional[str] = None) -> None:
    """Initialize the meme generator with output directory"""
    global generator, output_directory
    generator = MemeGenerator(templates_dir)
    output_directory = output_dir


@register_tool("generate_meme")
async def generate_meme(
    template: str,
    texts: Dict[str, str],
    font_size_override: Optional[Dict[str, int]] = None,
    auto_resize: bool = True,
    upload: bool = True,
) -> Dict[str, Any]:
    """Generate a meme from a template with visual feedback thumbnail and optional upload

    Args:
        template: Template ID to use
        texts: Dictionary of text for each area (e.g., {"top": "text", "bottom": "text"})
        font_size_override: Optional custom font sizes for specific areas
        auto_resize: Whether to automatically resize text to fit
        upload: Whether to upload the meme and return a shareable URL (default: True)
    """
    if generator is None:
        return {"success": False, "error": "Meme generator not initialized"}

    # Generate full-size meme with PIL image returned for thumbnail creation
    result = generator.generate_meme(
        template,
        texts,
        font_size_override,
        auto_resize,
        thumbnail_only=False,
        return_pil_image=True,  # Request PIL image for efficient thumbnail generation
    )

    if result.get("success"):
        # Save full-size image to file
        import base64
        import tempfile
        import time

        # Use output_directory (server ensures it exists)
        save_dir = output_directory if output_directory else tempfile.gettempdir()

        # Create unique filename
        timestamp = int(time.time())
        output_path = os.path.join(save_dir, f"meme_{template}_{timestamp}_{os.getpid()}.png")

        img_data = base64.b64decode(result["image_data"])
        with open(output_path, "wb") as f:
            f.write(img_data)

        # Upload the meme if requested
        share_url = None
        upload_info = {}
        if upload:
            try:
                from .upload import MemeUploader

                upload_result = MemeUploader.upload(output_path, service="auto")
                if upload_result["success"]:
                    share_url = upload_result["url"]
                    embed_url = upload_result.get("embed_url", share_url)  # Use embed_url if available
                    upload_info = {
                        "service": upload_result.get("service"),
                        "note": upload_result.get("note", ""),
                        "embed_url": embed_url,  # Include direct link for embedding
                    }
                else:
                    # Log but don't fail if upload doesn't work
                    upload_info = {"error": upload_result.get("error", "Upload failed")}
                    if upload_result.get("details"):
                        upload_info["details"] = upload_result["details"]
            except Exception as e:
                upload_info = {"error": f"Upload error: {str(e)}"}

        # Create thumbnail from the already-generated PIL image (optimization)
        if "pil_image" in result:
            # Use the existing PIL image to create thumbnail - avoids re-rendering
            thumbnail_result = generator.create_thumbnail_from_image(result["pil_image"])
        else:
            # Fallback to old method if PIL image not available
            thumbnail_result = generator.generate_meme(
                template,
                texts,
                font_size_override,
                auto_resize,
                thumbnail_only=True,
            )

        # Build response
        response = {
            "success": True,
            "output_path": output_path,
            "template_used": result.get("template_used"),
            "text_positions": result.get("text_positions"),
            "visual_feedback": {
                "format": "webp",
                "encoding": "base64",
                "data": thumbnail_result.get("image_data", ""),  # Use thumbnail data
                "size_kb": thumbnail_result.get("size_kb", 0),
            },
            "full_size_kb": result.get("size_kb", 0),
            "message": f"Meme generated and saved to {output_path}",
        }

        # Add share URL if upload was successful
        if share_url:
            response["share_url"] = share_url
            response["upload_info"] = upload_info
            # Include embed URL for GitHub/Markdown embedding
            if upload_info.get("embed_url"):
                response["embed_url"] = upload_info["embed_url"]
                response["message"] += f"\n🔗 Share URL: {share_url}"
                response["message"] += f"\n📎 Embed URL: {upload_info['embed_url']}"
            else:
                response["message"] += f"\n🔗 Share URL: {share_url}"
        elif upload and upload_info.get("error"):
            response["upload_error"] = upload_info["error"]
            if upload_info.get("details"):
                response["upload_error_details"] = upload_info["details"]

        return response

    # Error case
    if "image_data" in result:
        del result["image_data"]
    return result


@register_tool("list_meme_templates")
async def list_meme_templates() -> Dict[str, Any]:
    """List all available meme templates"""
    if generator is None:
        return {"success": False, "error": "Meme generator not initialized"}

    return generator.list_templates()


@register_tool("get_meme_template_info")
async def get_meme_template_info(template_id: str) -> Dict[str, Any]:
    """Get detailed information about a meme template"""
    if generator is None:
        return {"success": False, "error": "Meme generator not initialized"}

    return generator.get_template_info(template_id)


@register_tool("test_minimal")
async def test_minimal() -> Dict[str, Any]:
    """Minimal test tool that returns a tiny response"""
    # Test if generator affects response size
    result = {"success": True, "message": "This is a minimal response", "size": 42}
    if generator:
        result["generator_exists"] = True
        result["num_templates"] = len(generator.templates)
    return result


@register_tool("test_fake_meme")
async def test_fake_meme(template: str, texts: Dict[str, str]) -> Dict[str, Any]:
    """Test meme generation without actually creating an image"""
    # Don't do any image processing at all
    return {
        "success": True,
        "output_path": "/tmp/fake_meme.webp",
        "template_used": template,
        "text_positions": {"top": {"lines": [texts.get("top", "")], "font_size": 40}},
        "thumbnail_saved": True,
        "size_kb": 2.5,
        "message": "Fake meme generated (no actual image created)",
    }
