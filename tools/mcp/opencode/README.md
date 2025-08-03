# OpenCode MCP Server

The OpenCode MCP Server provides an HTTP/stdio interface for AI-powered code generation using OpenCode.

## Overview

This MCP server wraps the OpenCode CLI agent to provide:
- Code generation with context and history
- Code refactoring
- Code review and analysis
- Multi-language support
- State management with conversation history

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY` - **Required**: Your OpenRouter API key
- `OPENCODE_ENABLED` - Enable/disable the server (default: true)
- `OPENCODE_MODEL` - Model to use (default: qwen/qwen-2.5-coder-32b-instruct)
- `OPENCODE_TIMEOUT` - Request timeout in seconds (default: 300)
- `OPENCODE_MAX_CONTEXT` - Maximum context length (default: 8000)
- `OPENCODE_LOG_GENERATIONS` - Log all generations (default: true)
- `OPENCODE_INCLUDE_HISTORY` - Include conversation history (default: true)
- `OPENCODE_MAX_HISTORY` - Maximum history entries (default: 5)

### Configuration File

You can also create `opencode-config.json` in your project root:

```json
{
  "enabled": true,
  "model": "qwen/qwen-2.5-coder-32b-instruct",
  "timeout": 300,
  "max_context_length": 8000
}
```

## Running the Server

### Local Development

```bash
# Set your API key
export OPENROUTER_API_KEY="your-api-key-here"

# Run in HTTP mode (default)
python -m tools.mcp.opencode.server --mode http

# Run in stdio mode (for MCP integrations)
python -m tools.mcp.opencode.server --mode stdio
```

### Docker

```bash
# Using docker-compose
docker-compose up -d mcp-opencode

# Or run directly
docker run -p 8014:8014 -e OPENROUTER_API_KEY="your-key" mcp-opencode
```

## Available Tools

### generate_code
Generate code based on a prompt with optional context.

Parameters:
- `prompt` (required): The coding task or question
- `context`: Additional context or existing code
- `language`: Programming language (optional)
- `include_tests`: Include unit tests (default: false)
- `plan_mode`: Use plan mode for multi-step tasks (default: false)

### refactor_code
Refactor existing code according to instructions.

Parameters:
- `code` (required): The code to refactor
- `instructions` (required): Refactoring instructions
- `preserve_functionality`: Ensure functionality is preserved (default: true)

### review_code
Review code and provide feedback.

Parameters:
- `code` (required): The code to review
- `focus_areas`: Specific areas to focus on (array of strings)

### clear_opencode_history
Clear the conversation history.

### opencode_status
Get server status and statistics.

## Testing

```bash
# Run the test script
python tools/mcp/opencode/scripts/test_server.py

# Or use curl for manual testing
curl http://localhost:8014/health
curl http://localhost:8014/tools
```

## Integration with Claude

Once the server is running, it will be available as MCP tools in Claude:
- `mcp__opencode__generate_code`
- `mcp__opencode__refactor_code`
- `mcp__opencode__review_code`
- etc.

## Troubleshooting

1. **Server won't start**: Check that port 8014 is not in use
2. **API errors**: Ensure OPENROUTER_API_KEY is set correctly
3. **Container issues**: Make sure the openrouter-agents container is running
4. **Timeout errors**: Increase OPENCODE_TIMEOUT for complex tasks
