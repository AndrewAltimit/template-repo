# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running Tests
```bash
# Run all tests with coverage
pytest tests/ -v --cov=. --cov-report=xml

# Run a specific test file
pytest tests/test_mcp_tools.py -v

# Run tests with specific test name pattern
pytest -k "test_format" -v
```

### Code Quality
```bash
# Format code with Black
black .

# Check formatting without making changes
black --check .

# Run linting
flake8 .
pylint tools/ scripts/

# Type checking
mypy . --ignore-missing-imports
```

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start MCP server locally
python tools/mcp/mcp_server.py

# Start MCP server via Docker
docker-compose up -d mcp-server

# Run the main application
python main.py

# Test MCP server
python scripts/test-mcp-server.py
```

### Docker Operations
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Stop services
docker-compose down

# Rebuild after changes
docker-compose build mcp-server
```

## Architecture

### MCP Server Architecture
The project centers around a Model Context Protocol (MCP) server that provides various AI and development tools:

1. **FastAPI Server** (`tools/mcp/mcp_server.py`): Main HTTP API exposing MCP tools
2. **Tool Categories**:
   - **Code Quality**: format_check, lint, analyze, full_ci
   - **AI Integration**: consult_gemini, create_manim_animation, compile_latex
   - **Remote Services**: ComfyUI (image generation), AI Toolkit (LoRA training)

3. **HTTP Bridges** (`scripts/mcp-http-bridge.py`): Connects remote services to MCP server
4. **Configuration** (`mcp-config.json`): Defines available tools, security settings, and rate limits

### GitHub Actions Integration
The repository includes comprehensive CI/CD workflows:
- **PR Validation**: Automatic Gemini AI code review on pull requests
- **Testing Pipeline**: pytest with coverage reporting
- **Code Quality**: Multi-stage linting (Black, Flake8, MyPy, Pylint)
- **Self-hosted Runners**: Scripts for setting up local GitHub Actions runners

### Key Integration Points
1. **AI Services**: 
   - Gemini API for code review and consultation
   - Support for Claude and OpenAI integrations
   - Remote ComfyUI workflows for image generation

2. **Testing Strategy**:
   - Unit tests in `tests/` directory
   - Mock external dependencies (subprocess, HTTP calls)
   - Async test support with pytest-asyncio

3. **Client Pattern** (`main.py`):
   - MCPClient class for interacting with MCP server
   - Example workflow demonstrating tool usage
   - Environment-based configuration

### Security Considerations
- API key management via environment variables
- Rate limiting configured in mcp-config.json
- Docker network isolation for services
- No hardcoded credentials in codebase