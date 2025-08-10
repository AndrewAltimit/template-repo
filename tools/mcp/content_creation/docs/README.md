# Content Creation MCP Server

The Content Creation MCP Server provides tools for creating mathematical animations with Manim and compiling LaTeX documents to various formats.

## Features

- **Manim Animations**: Create beautiful mathematical animations
- **LaTeX Compilation**: Compile documents to PDF, DVI, or PostScript
- **TikZ Diagrams**: Render TikZ diagrams as standalone images
- **Multiple Output Formats**: Support for various output formats
- **Template Support**: Built-in document templates

## Available Tools

### create_manim_animation

Create mathematical animations using the Manim library.

**Parameters:**
- `script` (required): Python script containing Manim scene
- `output_format`: Animation format (default: "mp4")
  - Options: mp4, gif, png, webm
- `quality`: Rendering quality (default: "medium")
  - Options: low, medium, high, fourk
- `preview`: Generate preview frame only (default: false)

**Example:**
```json
{
  "tool": "create_manim_animation",
  "arguments": {
    "script": "from manim import *\n\nclass MyScene(Scene):\n    def construct(self):\n        self.play(Create(Circle()))",
    "output_format": "mp4",
    "quality": "medium"
  }
}
```

### compile_latex

Compile LaTeX documents to various formats with optional visual feedback.

**Parameters:**
- `content` (required): LaTeX document content
- `format`: Output format (default: "pdf")
  - Options: pdf, dvi, ps
- `template`: Document template (default: "article")
  - Options: article, report, book, beamer, custom
- `visual_feedback`: Return PNG preview image for visual verification (default: true)
  - When enabled, returns a base64-encoded JPEG preview of the first page

**Example:**
```json
{
  "tool": "compile_latex",
  "arguments": {
    "content": "\\section{Introduction}\nThis is my document.",
    "format": "pdf",
    "template": "article",
    "visual_feedback": true
  }
}
```

**Response Structure:**
```json
{
  "success": true,
  "output_path": "/app/output/latex/document_12345.pdf",
  "format": "pdf",
  "visual_feedback": {
    "format": "jpeg",
    "encoding": "base64",
    "data": "<base64_encoded_image>",
    "size_kb": 45.2
  }
}
```

### render_tikz

Render TikZ diagrams as standalone images.

**Parameters:**
- `tikz_code` (required): TikZ code for the diagram
- `output_format`: Output format (default: "pdf")
  - Options: pdf, png, svg

**Example:**
```json
{
  "tool": "render_tikz",
  "arguments": {
    "tikz_code": "\\begin{tikzpicture}\n  \\draw (0,0) circle (1);\n\\end{tikzpicture}",
    "output_format": "png"
  }
}
```

## Running the Server

### HTTP Mode

```bash
python -m tools.mcp.content_creation.server --mode http --output-dir /path/to/output
```

The server will start on port 8011 by default.

### stdio Mode (for Claude Desktop)

```bash
python -m tools.mcp.content_creation.server --mode stdio
```

## Requirements

The following tools must be installed for full functionality:

### For LaTeX
- `pdflatex` - PDF compilation
- `latex` - DVI compilation
- `dvips` - PostScript conversion
- `pdftoppm` - PDF to PNG conversion (optional)
- `pdf2svg` - PDF to SVG conversion (optional)

### For Manim
- `manim` - Mathematical animation library
- Python 3.7+
- FFmpeg (for video rendering)

## Docker Support

The Content Creation MCP Server runs in a container with all dependencies pre-installed:

### Using Docker Compose (Recommended)

```bash
# Start the server
docker-compose up -d mcp-content-creation

# View logs
docker-compose logs -f mcp-content-creation

# Stop the server
docker-compose down mcp-content-creation
```

### Docker Image Details

The server uses a custom Docker image with:
- Python 3.11 base image
- Complete TeXLive installation for LaTeX support
- Manim and its dependencies (FFmpeg, Cairo, Pango)
- Pillow for image processing and visual feedback
- PDF manipulation tools (poppler-utils, pdf2svg)

The Dockerfile is located at `docker/mcp-content.Dockerfile`.

## Output Directory Structure

The server organizes output files in subdirectories:

```
/app/output/
├── manim/      # Manim animations
│   ├── animation_12345.mp4
│   └── media/  # Manim working directory
└── latex/      # LaTeX documents
    ├── document_12345.pdf
    └── document_12345.log
```

## Configuration

### Environment Variables

- `MCP_CONTENT_PORT`: Server port (default: 8011)
- `MCP_CONTENT_OUTPUT_DIR`: Output directory (default: /app/output)
- `MCP_CONTENT_LOG_LEVEL`: Logging level (default: INFO)

## Examples

### Creating a Manim Animation

```python
# Example Manim script
script = """
from manim import *

class FourierSeries(Scene):
    def construct(self):
        # Create axes
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            axis_config={"color": BLUE}
        )

        # Create function graph
        func = axes.plot(lambda x: np.sin(x), color=YELLOW)

        # Animate
        self.play(Create(axes), Create(func))
        self.wait(2)
"""

# Send to server
response = requests.post("http://localhost:8011/mcp/execute", json={
    "tool": "create_manim_animation",
    "arguments": {
        "script": script,
        "quality": "high"
    }
})
```

### Compiling a LaTeX Document

```python
# Example LaTeX content
content = r"""
\documentclass{article}
\usepackage{amsmath}
\title{Mathematical Formulas}
\author{MCP Server}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}
This document demonstrates LaTeX compilation via MCP.

\section{Formulas}
The quadratic formula is:
\begin{equation}
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
\end{equation}

\end{document}
"""

# Send to server
response = requests.post("http://localhost:8011/mcp/execute", json={
    "tool": "compile_latex",
    "arguments": {
        "content": content,
        "template": "custom"
    }
})
```

## Error Handling

The server provides detailed error messages:

- **Missing dependencies**: Clear message about which tool needs to be installed
- **Compilation errors**: LaTeX error messages from the log file
- **Rendering failures**: Manim error output
- **File not found**: Descriptive error messages

## Performance Considerations

- **Manim animations** can be CPU-intensive
  - Use `quality: "low"` for quick previews
  - Use `preview: true` to generate only the final frame
  - Higher quality settings ("high", "fourk") take significantly longer

- **LaTeX compilation** runs twice to resolve references
  - First pass: Generate auxiliary files
  - Second pass: Resolve cross-references and citations
  - Large documents may require additional passes

- **Visual feedback** optimization
  - Images are automatically compressed to JPEG format
  - Maximum size limit of 100KB for feedback images
  - Lower DPI (72) used for preview generation

- **Resource usage**
  - Consider container memory limits for large documents
  - Temporary files are cleaned up after processing
  - Output directory should have sufficient space

## Testing

Run the test script to verify the server is working:

```bash
# Test the server directly
python tools/mcp/content_creation/scripts/test_server.py

# Or run through Docker
docker-compose run --rm python-ci python tools/mcp/content_creation/scripts/test_server.py
```

The test script will:
1. Check server health and connectivity
2. List available tools and their parameters
3. Test LaTeX compilation with visual feedback
4. Test TikZ diagram rendering
5. Test Manim animation creation (mp4, gif, png formats)
6. Verify error handling for invalid inputs
7. Test preview generation modes
8. Validate output file creation and cleanup
