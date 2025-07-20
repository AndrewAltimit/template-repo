# Code Quality MCP Server

The Code Quality MCP Server provides tools for checking and enforcing code formatting and linting standards across multiple programming languages.

## Features

- **Multi-language support**: Python, JavaScript, TypeScript, Go, Rust
- **Format checking**: Verify code follows formatting standards
- **Auto-formatting**: Automatically fix formatting issues
- **Linting**: Static code analysis with multiple linters
- **Configurable**: Support for custom linting configurations

## Available Tools

### format_check

Check if code follows formatting standards for the specified language.

**Parameters:**
- `path` (required): Path to file or directory to check
- `language`: Programming language (default: "python")
  - Options: python, javascript, typescript, go, rust

**Example:**
```json
{
  "tool": "format_check",
  "arguments": {
    "path": "src/main.py",
    "language": "python"
  }
}
```

### lint

Run static code analysis using various linters.

**Parameters:**
- `path` (required): Path to file or directory to lint
- `linter`: Linter to use (default: "flake8")
  - Options: flake8, pylint, eslint, golint, clippy
- `config`: Path to linting configuration file

**Example:**
```json
{
  "tool": "lint",
  "arguments": {
    "path": "src/",
    "linter": "flake8",
    "config": ".flake8"
  }
}
```

### autoformat

Automatically format code files according to language standards.

**Parameters:**
- `path` (required): Path to file or directory to format
- `language`: Programming language (default: "python")
  - Options: python, javascript, typescript, go, rust

**Example:**
```json
{
  "tool": "autoformat",
  "arguments": {
    "path": "src/main.py",
    "language": "python"
  }
}
```

## Running the Server

### HTTP Mode

```bash
python -m tools.mcp.code_quality.server --mode http
```

The server will start on port 8010 by default.

### stdio Mode (for Claude Desktop)

```bash
python -m tools.mcp.code_quality.server --mode stdio
```

## Requirements

The following tools must be installed for full functionality:

### Python
- `black` - Code formatter
- `flake8` - Linter
- `pylint` - Advanced linter (optional)

### JavaScript/TypeScript
- `prettier` - Code formatter
- `eslint` - Linter

### Go
- `gofmt` - Code formatter
- `golint` - Linter

### Rust
- `rustfmt` - Code formatter
- `clippy` - Linter

## Docker Support

The Code Quality MCP Server can run in a container with all dependencies pre-installed:

```dockerfile
FROM python:3.11-slim

# Install formatters and linters
RUN pip install black flake8 pylint
RUN npm install -g prettier eslint
RUN apt-get update && apt-get install -y golang-go rustfmt

# Copy server code
COPY tools/mcp/code_quality /app/code_quality
COPY tools/mcp/core /app/core

WORKDIR /app
CMD ["python", "-m", "code_quality.server"]
```

## Configuration

### Environment Variables

- `MCP_CODE_QUALITY_PORT`: Server port (default: 8010)
- `MCP_CODE_QUALITY_LOG_LEVEL`: Logging level (default: INFO)

### Linting Configuration

Each linter supports its own configuration format:

- **flake8**: `.flake8` or `setup.cfg`
- **pylint**: `.pylintrc`
- **eslint**: `.eslintrc.json` or `.eslintrc.js`

## Testing

Run the test script to verify the server is working:

```bash
python tools/mcp/code_quality/scripts/test_server.py
```

## Integration with CI/CD

The Code Quality MCP Server can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Start Code Quality Server
  run: |
    python -m tools.mcp.code_quality.server --mode http &
    sleep 2

- name: Check Code Formatting
  run: |
    curl -X POST http://localhost:8010/mcp/execute \
      -H "Content-Type: application/json" \
      -d '{
        "tool": "format_check",
        "arguments": {"path": ".", "language": "python"}
      }'
```

## Error Handling

The server provides detailed error messages:

- Missing tools: Clear message about which tool needs to be installed
- Unsupported languages/linters: List of supported options
- File not found: Descriptive error message
- Configuration issues: Details about what went wrong

## Performance Considerations

- The server processes files sequentially
- Large directories may take time to process
- Consider using specific file paths instead of directories when possible
- Results are not cached between requests
