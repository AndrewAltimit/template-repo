# MCP Tools Documentation

This document provides detailed information about the containerized MCP (Model Context Protocol) tools in this project.

## Container-First Design

All MCP tools run in Docker containers as part of this project's philosophy:

- **Zero local dependencies** - just Docker
- **Consistent execution** - same results on any Linux system
- **Easy deployment** - works identically on self-hosted runners
- **Single maintainer friendly** - no complex setup or coordination needed

## Table of Contents

- [Overview](#overview)
- [Core Tools](#core-tools)
- [AI Integration Tools](#ai-integration-tools)
- [Content Creation Tools](#content-creation-tools)
- [Remote Services](#remote-services)
- [Custom Tool Development](#custom-tool-development)

## Overview

MCP tools are functions that can be executed through the MCP server to perform various development and content creation tasks. They are accessible via HTTP API or through the MCP protocol.

### Tool Execution

All tools can be executed via POST request to `/tools/execute`:

```bash
curl -X POST http://localhost:8005/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "tool_name",
    "arguments": {
      "arg1": "value1",
      "arg2": "value2"
    }
  }'
```

## Core Tools

### format_check

Check code formatting according to language-specific standards.

**Parameters:**

- `path` (string): Path to the file or directory to check
- `language` (string): Programming language (python, javascript, typescript, go, rust)

**Example:**

```python
{
  "tool": "format_check",
  "arguments": {
    "path": "./src",
    "language": "python"
  }
}
```

**Response:**

```json
{
  "formatted": true,
  "output": "All files formatted correctly"
}
```

### lint

Run static code analysis to find potential issues.

**Parameters:**

- `path` (string): Path to analyze
- `config` (string, optional): Path to linting configuration file

**Example:**

```python
{
  "tool": "lint",
  "arguments": {
    "path": "./src",
    "config": ".flake8"
  }
}
```

**Response:**

```json
{
  "success": true,
  "issues": [
    "src/main.py:10:1: E302 expected 2 blank lines, found 1"
  ]
}
```

### analyze

Perform deep static analysis using advanced tools.

**Parameters:**

- `path` (string): Path to analyze
- `depth` (integer): Analysis depth level (1-5)

**Example:**

```python
{
  "tool": "analyze",
  "arguments": {
    "path": "./src",
    "depth": 3
  }
}
```

## AI Integration Tools

### consult_gemini

Get AI assistance from Google's Gemini model for technical questions, code review, and suggestions.

**Parameters:**

- `question` (string): The question or request
- `context` (string, optional): Additional context or code

**Example:**

```python
{
  "tool": "consult_gemini",
  "arguments": {
    "question": "How can I optimize this function for better performance?",
    "context": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
  }
}
```

**Response:**

```json
{
  "response": "The current implementation has exponential time complexity. Here's an optimized version using memoization...",
  "model": "gemini-pro",
  "tokens_used": 245
}
```

### clear_gemini_history

Clear Gemini's conversation history to ensure fresh responses without cached context.

**Parameters:**

- None

**Example:**

```python
{
  "tool": "clear_gemini_history",
  "arguments": {}
}
```

**Response:**

```json
{
  "status": "success",
  "message": "Cleared 5 conversation entries",
  "cleared_entries": 5
}
```

**Use Cases:**

- Before PR reviews to ensure fresh analysis
- When switching between different contexts
- To reset after errors or incorrect responses

### Advanced Gemini Features

The Gemini integration supports several specialized functions:

1. **Code Analysis**

   ```python
   gemini.analyze_code(code, language="python")
   ```

2. **Error Explanation**

   ```python
   gemini.explain_error(error_message, code_context)
   ```

3. **Documentation Generation**

   ```python
   gemini.generate_documentation(code, style="google")
   ```

4. **Test Suggestion**

   ```python
   gemini.suggest_tests(code, framework="pytest")
   ```

## Content Creation Tools

### create_manim_animation

Create mathematical and technical animations using Manim.

**Parameters:**

- `script` (string): Manim Python script
- `output_format` (string): Output format (mp4, gif, webm)

**Example:**

```python
{
  "tool": "create_manim_animation",
  "arguments": {
    "script": "from manim import *\n\nclass Example(Scene):\n    def construct(self):\n        text = Text('Hello, MCP!')\n        self.play(Write(text))",
    "output_format": "mp4"
  }
}
```

**Response:**

```json
{
  "success": true,
  "output_path": "/app/output/manim/Example.mp4",
  "format": "mp4"
}
```

### compile_latex

Compile LaTeX documents to various formats.

**Parameters:**

- `content` (string): LaTeX document content
- `format` (string): Output format (pdf, dvi, ps)

**Example:**

```python
{
  "tool": "compile_latex",
  "arguments": {
    "content": "\\documentclass{article}\\begin{document}\\title{Test}\\maketitle\\end{document}",
    "format": "pdf"
  }
}
```

**Response:**

```json
{
  "success": true,
  "output_path": "/app/output/latex/document_12345.pdf",
  "format": "pdf"
}
```

## Remote Services

### ComfyUI Integration

Access ComfyUI workflows for image generation.

**Available Tools:**

- `generate_image`: Generate images using workflows
- `list_workflows`: List available workflows
- `execute_workflow`: Execute specific workflow

**Configuration:**

```bash
COMFYUI_SERVER_URL=http://192.168.0.152:8189
```

### AI Toolkit Integration

Train LoRA models using AI Toolkit.

**Available Tools:**

- `upload_dataset`: Upload training dataset
- `create_training_config`: Configure training parameters
- `start_training`: Begin training job
- `check_training_status`: Monitor progress
- `list_models`: List trained models

**Configuration:**

```bash
AI_TOOLKIT_SERVER_URL=http://192.168.0.152:8190
```

## Custom Tool Development

### Creating a New Tool

1. **Define the tool function:**

```python
# tools/mcp/custom_tools.py
async def my_custom_tool(param1: str, param2: int = 10) -> Dict[str, Any]:
    """
    My custom tool description.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary with results
    """
    # Tool implementation
    result = process_data(param1, param2)

    return {
        "success": True,
        "result": result,
        "metadata": {
            "param1": param1,
            "param2": param2
        }
    }
```

2. **Register in MCP server:**

```python
# tools/mcp/mcp_server.py
TOOLS = {
    # ... existing tools
    "my_custom_tool": custom_tools.my_custom_tool,
}
```

3. **Update configuration:**

```json
// mcp-config.json
{
  "tools": {
    "my_custom_tool": {
      "description": "My custom tool description",
      "parameters": {
        "param1": {
          "type": "string",
          "description": "Description of param1",
          "required": true
        },
        "param2": {
          "type": "integer",
          "description": "Description of param2",
          "default": 10
        }
      }
    }
  }
}
```

### Tool Guidelines

1. **Error Handling:**
   - Always return structured responses
   - Include error details in response
   - Use try-except blocks

2. **Async Operations:**
   - Use `async/await` for I/O operations
   - Handle timeouts appropriately
   - Consider concurrent execution

3. **Input Validation:**
   - Validate all parameters
   - Provide helpful error messages
   - Use type hints

4. **Output Format:**
   - Return consistent structure
   - Include success status
   - Provide meaningful metadata

### Testing Tools

```python
# tests/test_custom_tool.py
import pytest
from tools.mcp.custom_tools import my_custom_tool

@pytest.mark.asyncio
async def test_my_custom_tool():
    result = await my_custom_tool("test", 42)

    assert result["success"] is True
    assert result["result"] is not None
    assert result["metadata"]["param1"] == "test"
    assert result["metadata"]["param2"] == 42
```

## Best Practices

### Performance

1. **Caching:**
   - Cache expensive operations
   - Use Redis for distributed caching
   - Set appropriate TTL values

2. **Concurrency:**
   - Use asyncio for I/O-bound operations
   - Implement rate limiting
   - Handle concurrent requests properly

### Security

1. **Input Sanitization:**
   - Validate all user inputs
   - Escape special characters
   - Limit resource usage

2. **Authentication:**
   - Implement API key authentication
   - Use secure communication (HTTPS)
   - Log access attempts

### Monitoring

1. **Logging:**
   - Log all tool executions
   - Include timing information
   - Track error rates

2. **Metrics:**
   - Monitor tool usage
   - Track response times
   - Alert on failures

## Troubleshooting

### Common Issues

1. **Tool not found:**
   - Check tool registration in MCP server
   - Verify configuration file
   - Restart MCP server

2. **Timeout errors:**
   - Increase timeout in configuration
   - Optimize tool performance
   - Check network connectivity

3. **Permission errors:**
   - Verify file permissions
   - Check Docker volume mounts
   - Review security settings

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
docker-compose up mcp-server
```

View logs:

```bash
docker-compose logs -f mcp-server
```

## API Reference

### Endpoints

- `GET /` - Server information
- `GET /health` - Health check
- `GET /tools` - List available tools
- `POST /tools/execute` - Execute a tool
- `GET /tools/{tool_name}` - Get tool details

### Response Format

```json
{
  "success": true,
  "result": {
    // Tool-specific results
  },
  "error": null,
  "metadata": {
    "tool": "tool_name",
    "execution_time": 1.23,
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

### Error Codes

- `400` - Bad Request (invalid parameters)
- `404` - Tool not found
- `500` - Internal server error
- `503` - Service unavailable
