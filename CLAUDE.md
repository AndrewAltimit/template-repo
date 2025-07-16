# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is a **single-maintainer project** by @AndrewAltimit with a **container-first philosophy**:

- All Python operations run in Docker containers
- Self-hosted infrastructure for zero-cost operation
- Designed for maximum portability - works on any Linux system with Docker
- No contributors model - optimized for individual developer efficiency

## AI Agent Collaboration

You are working alongside two other AI agents:

1. **Gemini CLI** - Handles automated PR code reviews
2. **GitHub Copilot** - Provides code review suggestions in PRs

Your role as Claude Code is the primary development assistant, handling:

- Architecture decisions and implementation
- Complex refactoring and debugging
- Documentation and test writing
- CI/CD pipeline development

## Commands

### Running Tests

```bash
# Run all tests with coverage (containerized)
docker-compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml

# Run a specific test file
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v

# Run tests with specific test name pattern
docker-compose run --rm python-ci pytest -k "test_format" -v

# Quick test run using helper script
./scripts/run-ci.sh test
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

# Run all checks at once
./scripts/run-ci.sh full
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

# Start Gemini MCP server (MUST run on host, not in container)
python tools/mcp/gemini_mcp_server.py

# Test Gemini MCP server (port 8006)
curl http://localhost:8006/health

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

The project uses multiple Model Context Protocol (MCP) servers to provide various AI and development tools:

1. **Main MCP Server** (`tools/mcp/mcp_server.py`): HTTP API on port 8005
   - **Code Quality**:
     - `format_check` - Check code formatting (Python, JS, TS, Go, Rust)
     - `lint` - Run static analysis with optional config
   - **Content Creation**:
     - `create_manim_animation` - Create mathematical/technical animations
     - `compile_latex` - Generate PDF/DVI/PS documents from LaTeX

2. **Gemini MCP Server** (`tools/mcp/gemini_mcp_server.py`): HTTP API on port 8006
   - **MUST run on host system** (not in container) due to Docker requirements
   - **AI Integration**:
     - `consult_gemini` - Get AI assistance for technical questions
     - `clear_gemini_history` - Clear conversation history for fresh responses
   - Automatically exits with error if launched in container

3. **Remote Services**: ComfyUI (image generation), AI Toolkit (LoRA training)

4. **Containerized CI/CD**:
   - **Python CI Container** (`docker/python-ci.Dockerfile`): All Python tools (Black, isort, flake8, pylint, mypy, pytest)
   - **Helper Scripts**: Centralized CI operations to reduce workflow complexity
   - **Cache Prevention**: PYTHONDONTWRITEBYTECODE=1, pytest cache disabled

4. **Configuration** (`.mcp.json`): Defines available tools, security settings, and rate limits

### GitHub Actions Integration

The repository includes comprehensive CI/CD workflows:

- **PR Validation**: Automatic Gemini AI code review with history clearing
- **Testing Pipeline**: Containerized pytest with coverage reporting
- **Code Quality**: Multi-stage linting in Docker containers
- **Self-hosted Runners**: All workflows run on self-hosted infrastructure
- **Runner Maintenance**: Automated cleanup and health checks

### Container Architecture Philosophy

1. **Everything Containerized**:
   - Python CI/CD tools run in `python-ci` container (Python 3.11)
   - MCP server runs in its own container
   - Only exception: Gemini CLI (would require Docker-in-Docker)
   - All containers run with user permissions (non-root)

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
   - All tests run in containers with Python 3.11
   - Mock external dependencies (subprocess, HTTP calls)
   - Async test support with pytest-asyncio
   - Coverage reporting with pytest-cov
   - No pytest cache to avoid permission issues

3. **Client Pattern** (`main.py`):
   - MCPClient class for interacting with MCP server
   - Example workflow demonstrating tool usage
   - Environment-based configuration

### Security Considerations

- API key management via environment variables
- Rate limiting configured in .mcp.json
- Docker network isolation for services
- No hardcoded credentials in codebase
- Containers run as non-root user

## Development Reminders

- IMPORTANT: When you have completed a task, you MUST run the lint and quality checks:
  ```bash
  # Run full CI checks
  ./scripts/run-ci.sh full

  # Or individual checks
  ./scripts/run-ci.sh format
  ./scripts/run-ci.sh lint-basic
  ./scripts/run-ci.sh lint-full
  ```
- NEVER commit changes unless the user explicitly asks you to
- Always follow the container-first philosophy - use Docker for all Python operations
- Remember that Gemini CLI cannot be containerized (needs Docker access)
- Use pytest fixtures and mocks for testing external dependencies

## AI Toolkit & ComfyUI Integration Notes

When working with the remote MCP servers (AI Toolkit and ComfyUI):

1. **Dataset Paths**: Always use absolute paths in AI Toolkit configs:
   - ✅ `/ai-toolkit/datasets/dataset_name`
   - ❌ `dataset_name` (will fail with "No such file or directory")

2. **LoRA Transfer**: For files >100MB, use chunked upload:
   - See `transfer_lora_between_services.py` for working implementation
   - Parameters: `upload_id` (provide UUID), `total_size` (bytes), `chunk` (not `chunk_data`)

3. **FLUX Workflows**: Different from SD workflows:
   - Use FluxGuidance node (guidance ~3.5)
   - KSampler: cfg=1.0, sampler="heunpp2", scheduler="simple"
   - Negative prompt cannot be null (use empty string)

4. **MCP Tool Discovery**: The `/mcp/tools` endpoint may not list all tools
   - Check the gist source directly for complete tool list
   - Chunked upload tools exist even if not shown

See `docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md` for comprehensive details.
