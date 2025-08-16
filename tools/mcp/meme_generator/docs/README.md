# Meme Generator MCP Server

Generate memes from templates with customizable text overlays and visual feedback.

## Overview

The Meme Generator MCP Server provides tools for creating memes from predefined templates with intelligent text placement, auto-resizing, and visual feedback for AI agents to confirm proper text rendering.

## Important: Understanding Meme Culture

**Before using this tool, please read the [MEME_USAGE_GUIDE.md](./MEME_USAGE_GUIDE.md)**

Memes are cultural artifacts with specific contexts, formats, and usage patterns. Using them incorrectly defeats their purpose. Each template includes:
- **Cultural context**: The origin and meaning
- **Text positioning**: Where text MUST appear (e.g., "Ol' Reliable" goes IN the spatula label)
- **Phrasing patterns**: How to structure the text
- **Tone and intent**: The emotional context

## Features

- **Template-Based Generation**: Pre-configured meme templates with optimal text areas
- **Auto-Resize Text**: Automatically adjusts font size to fit text within designated areas
- **Visual Feedback**: Returns base64-encoded images for AI agents to verify text placement
- **Automatic Upload**: Generates shareable URLs via free hosting services (0x0.st)
- **Custom Font Sizes**: Override default font sizes for specific text areas
- **Text Wrapping**: Intelligent text wrapping to fit within boundaries
- **Stroke Effects**: Text with outlines for better readability on any background
- **Cultural Documentation**: Each template includes usage rules and context

## Quick Start

### Using Docker (Recommended)

```bash
# Build and start the server
docker-compose up -d mcp-meme-generator

# Check logs
docker-compose logs -f mcp-meme-generator

# Test the server
python tools/mcp/meme_generator/scripts/test_server.py
```

### Local Development

```bash
# Install dependencies
pip install -r docker/requirements/requirements-meme.txt

# Start the server
python -m tools.mcp.meme_generator.server --mode http --port 8016

# Or with custom paths
python -m tools.mcp.meme_generator.server --templates /path/to/templates --output /path/to/output
```

## Available Tools

### 1. `generate_meme`
Generate a meme from a template with text overlays.

**Parameters:**
- `template` (string, required): Template ID (e.g., 'ol_reliable')
- `texts` (object, required): Text for each area (e.g., `{"top": "When...", "bottom": "Ol' Reliable"}`)
- `font_size_override` (object, optional): Custom font sizes for specific areas
- `auto_resize` (boolean, optional): Auto-adjust font size to fit text (default: true)
- `upload` (boolean, optional): Upload to get shareable URL (default: true)

**Example:**
```python
result = await generate_meme(
    template="ol_reliable",
    texts={
        "top": "When the code won't compile",
        "bottom": "print('hello world')"
    },
    auto_resize=True,
    upload=True  # Automatically uploads and returns share_url
)

# Response includes:
# - output_path: Local file path
# - share_url: https://0x0.st/XXXX.png (ready to share!)
# - visual_feedback: Thumbnail preview
```

**Sharing the Meme:**
```markdown
# Use the share_url directly in markdown
![My Meme](https://0x0.st/XXXX.png)
```

**Response:**
```json
{
  "success": true,
  "output_path": "/output/memes/meme_ol_reliable_12345.png",
  "template": "ol_reliable",
  "texts": {...},
  "visual_feedback": {
    "format": "jpeg",
    "encoding": "base64",
    "data": "...",
    "size_kb": 45.2
  },
  "text_positions": {
    "top": {
      "lines": ["When the code", "won't compile"],
      "font_size": 36,
      "positions": [[x1, y1], [x2, y2]]
    }
  },
  "size_kb": 120.5
}
```

### 2. `list_meme_templates`
List all available meme templates.

**Example:**
```python
result = await list_meme_templates()
```

**Response:**
```json
{
  "success": true,
  "templates": [
    {
      "id": "ol_reliable",
      "name": "Ol' Reliable",
      "description": "SpongeBob slapping his spatula...",
      "text_areas": ["top", "bottom"]
    }
  ]
}
```

### 3. `get_meme_template_info`
Get detailed information about a specific meme template.

**Parameters:**
- `template_id` (string, required): Template ID to get info for

**Example:**
```python
result = await get_meme_template_info(template_id="ol_reliable")
```

## Template Configuration

Templates are defined in JSON files in the `templates/config/` directory.

### Template Schema

```json
{
  "name": "Template Name",
  "template_file": "image.jpg",
  "description": "Template description",
  "text_areas": [
    {
      "id": "top",
      "position": {"x": 370, "y": 50},
      "width": 320,
      "height": 100,
      "default_font_size": 40,
      "max_font_size": 60,
      "min_font_size": 20,
      "text_align": "center",
      "text_color": "white",
      "stroke_color": "black",
      "stroke_width": 2,
      "max_chars": 30,
      "recommended_text": "When [situation]",
      "usage": "Describe the situation"
    }
  ],
  "usage_rules": [
    "Rule 1",
    "Rule 2"
  ],
  "examples": [
    {
      "top": "Example top text",
      "bottom": "Example bottom text"
    }
  ]
}
```

## Adding New Templates

1. **Add Template Image**: Place the image in `templates/` directory
2. **Create Configuration**: Create a JSON config in `templates/config/`
3. **Define Text Areas**: Specify position, size, and styling for each text area
4. **Set Usage Rules**: Document how the meme should be used
5. **Restart Server**: The server will automatically load new templates on restart

### Example: Adding Drake Meme Template

1. Download drake template image to `templates/drake.jpg`
2. Create `templates/config/drake.json`:

```json
{
  "name": "Drake",
  "template_file": "drake.jpg",
  "description": "Drake pointing meme for showing preferences",
  "text_areas": [
    {
      "id": "reject",
      "position": {"x": 450, "y": 125},
      "width": 280,
      "height": 100,
      "default_font_size": 32,
      "text_align": "center",
      "text_color": "black",
      "stroke_color": "white",
      "stroke_width": 1,
      "usage": "Thing being rejected"
    },
    {
      "id": "prefer",
      "position": {"x": 450, "y": 375},
      "width": 280,
      "height": 100,
      "default_font_size": 32,
      "text_align": "center",
      "text_color": "black",
      "stroke_color": "white",
      "stroke_width": 1,
      "usage": "Thing being preferred"
    }
  ],
  "usage_rules": [
    "Top text is what Drake rejects",
    "Bottom text is what Drake prefers",
    "Used to show preference between two options"
  ]
}
```

## Visual Feedback for AI Agents

The server provides visual feedback in the response, allowing AI agents to:

1. **Verify Text Placement**: Check if text fits within designated areas
2. **Detect Overflow**: Identify when text goes outside boundaries
3. **Adjust Settings**: Modify font size or shorten text based on visual confirmation
4. **Quality Control**: Ensure meme is readable and properly formatted

### Using Visual Feedback

```python
result = await generate_meme(...)

if result["success"]:
    # Visual feedback is in result["visual_feedback"]
    # It contains base64-encoded JPEG data

    # AI agent can analyze the image to verify:
    # - Text is within boundaries
    # - Text is readable
    # - No overlap between text areas

    if text_overflow_detected:
        # Retry with smaller font or shorter text
        result = await generate_meme(
            template="ol_reliable",
            texts={"top": "Shorter text", "bottom": "..."},
            font_size_override={"top": 30}
        )
```

## Environment Variables

- `MCP_OUTPUT_DIR`: Directory for saving generated memes (default: `/app/output`)
- `PORT`: HTTP server port (default: 8016)
- `PYTHONUNBUFFERED`: Set to 1 for immediate log output

## Docker Integration

The server runs in a Docker container with:
- Python 3.11
- Pillow for image processing
- Liberation fonts for text rendering
- Volume mount for template files
- Output directory for generated memes

## Testing

Run the comprehensive test suite:

```bash
# Test all functionality
python tools/mcp/meme_generator/scripts/test_server.py

# The test script will:
# - List available templates
# - Get template information
# - Generate memes with various settings
# - Test error handling
# - Save preview images for inspection
```

## Troubleshooting

### Font Issues
If text appears as boxes or missing characters:
- Ensure Liberation fonts are installed
- Check font path in `tools.py`
- Try using system default font as fallback

### Template Not Found
- Verify template image exists in `templates/` directory
- Check JSON config is in `templates/config/`
- Ensure JSON is valid (no syntax errors)
- Restart server after adding templates

### Text Overflow
- Enable `auto_resize` for automatic adjustment
- Reduce `font_size_override` values
- Shorten text content
- Adjust text area dimensions in template config

## Architecture

```
meme_generator/
├── server.py           # MCP server implementation
├── tools.py            # Core meme generation logic
├── templates/          # Template images
│   ├── config/         # Template configurations
│   │   ├── template_schema.json
│   │   └── ol_reliable.json
│   └── ol_reliable.jpg
├── scripts/
│   └── test_server.py  # Test suite
└── docs/
    └── README.md       # This file
```

## Integration with AI Agents

The Meme Generator MCP Server is designed for seamless integration with AI agents:

1. **Template Discovery**: Agents can list and explore available templates
2. **Intelligent Generation**: Auto-resize ensures text always fits
3. **Visual Verification**: Base64 image feedback for quality control
4. **Error Recovery**: Clear error messages for debugging
5. **Customization**: Override defaults when needed

## Performance

- Image generation: < 100ms typical
- Visual feedback encoding: < 50ms
- Memory usage: ~50MB base + image data
- Concurrent requests: Supported via async handlers

## Additional Documentation

- **[MEME_USAGE_GUIDE.md](./MEME_USAGE_GUIDE.md)** - Understanding meme culture and proper usage
- **[UPLOAD_GUIDE.md](./UPLOAD_GUIDE.md)** - How automatic upload and sharing works

## Security

- Read-only template access
- Sandboxed file operations
- External network calls only for optional upload feature
- Input validation on all parameters
- Safe image processing with Pillow

## Future Enhancements

- [ ] Support for animated GIF memes
- [ ] Custom font upload support
- [ ] Multi-language text support
- [ ] AI-powered text suggestions
- [ ] Template recommendation engine
- [ ] Batch meme generation
- [ ] Watermark support
- [ ] Social media optimization presets
