# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is a **single-maintainer project** by @AndrewAltimit with a **container-first philosophy**:
- All Python operations run in Docker containers
- Self-hosted infrastructure for zero-cost operation
- Designed for maximum portability - works on any Linux system with Docker
- No contributors model - optimized for individual developer efficiency

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
# Using containerized CI scripts (recommended)
./scripts/run-ci.sh format      # Check formatting
./scripts/run-ci.sh lint-basic   # Basic linting
./scripts/run-ci.sh lint-full    # Full linting suite
./scripts/run-ci.sh autoformat   # Auto-format code

# Direct Docker Compose commands
docker-compose run --rm python-ci black --check .
docker-compose run --rm python-ci flake8 .
docker-compose run --rm python-ci pylint tools/ scripts/
docker-compose run --rm python-ci mypy . --ignore-missing-imports

# Note: All Python CI/CD tools run in containers to ensure consistency
```

### Development
```bash
# Start MCP server via Docker (recommended)
docker-compose up -d mcp-server

# View MCP server logs
docker-compose logs -f mcp-server

# Test MCP server (port 8005)
curl http://localhost:8005/health
python scripts/test-mcp-server.py

# Run the main application
python main.py

# For local development without Docker
pip install -r requirements.txt
python tools/mcp/mcp_server.py
```

### Docker Operations
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f mcp-server
docker-compose logs -f python-ci

# Stop services
docker-compose down

# Rebuild after changes
docker-compose build mcp-server
docker-compose build python-ci
```

### Helper Scripts
```bash
# CI/CD operations script
./scripts/run-ci.sh [stage]
# Stages: format, lint-basic, lint-full, security, test, yaml-lint, json-lint, autoformat

# Lint stage helper (used in workflows)
./scripts/run-lint-stage.sh [stage]
# Stages: format, basic, full

# Fix runner permission issues
./scripts/fix-runner-permissions.sh
```

## Architecture

### MCP Server Architecture
The project centers around a Model Context Protocol (MCP) server that provides various AI and development tools:

1. **FastAPI Server** (`tools/mcp/mcp_server.py`): Main HTTP API on port 8005
2. **Tool Categories**:
   - **Code Quality**: format_check, lint, analyze, full_ci
   - **AI Integration**: consult_gemini, clear_gemini_history, create_manim_animation, compile_latex
   - **Remote Services**: ComfyUI (image generation), AI Toolkit (LoRA training)

3. **Containerized CI/CD**:
   - **Python CI Container** (`docker/python-ci.Dockerfile`): All Python tools (Black, isort, flake8, pylint, mypy, pytest)
   - **Helper Scripts**: Centralized CI operations to reduce workflow complexity
   - **Cache Prevention**: PYTHONDONTWRITEBYTECODE=1, pytest cache disabled

4. **Configuration** (`mcp-config.json`): Defines available tools, security settings, and rate limits

### GitHub Actions Integration
The repository includes comprehensive CI/CD workflows:
- **PR Validation**: Automatic Gemini AI code review with history clearing
- **Testing Pipeline**: Containerized pytest with coverage reporting  
- **Code Quality**: Multi-stage linting in Docker containers
- **Self-hosted Runners**: All workflows run on self-hosted infrastructure
- **Runner Maintenance**: Automated cleanup and health checks

### Container Architecture Philosophy
1. **Everything Containerized**:
   - Python CI/CD tools run in `python-ci` container
   - MCP server runs in its own container
   - Only exception: Gemini CLI (would require Docker-in-Docker)

2. **Zero Local Dependencies**:
   - No need to install Python, Node.js, or any tools locally
   - All operations available through Docker Compose
   - Portable across any Linux system

3. **Self-Hosted Infrastructure**:
   - All GitHub Actions run on self-hosted runners
   - No cloud costs or external dependencies
   - Full control over build environment

### Key Integration Points
1. **AI Services**: 
   - Gemini API for code review (runs on host due to Docker requirements)
   - Support for Claude and OpenAI integrations
   - Remote ComfyUI workflows for image generation

2. **Testing Strategy**:
   - All tests run in containers
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
- Containers run as non-root user