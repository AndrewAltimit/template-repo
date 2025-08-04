# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is a **single-maintainer project** by @AndrewAltimit with a **container-first philosophy**:

- All Python operations run in Docker containers
- Self-hosted infrastructure for zero-cost operation
- Designed for maximum portability - works on any Linux system with Docker
- No contributors model - optimized for individual developer efficiency

## AI Agent Collaboration

You are working alongside four other AI agents in a comprehensive ecosystem:

1. **Gemini CLI** - Handles automated PR code reviews
2. **GitHub Copilot** - Provides code review suggestions in PRs
3. **Issue Monitor Agent** - Automatically creates PRs from well-described issues
4. **PR Review Monitor Agent** - Automatically implements fixes based on review feedback

Your role as Claude Code is the primary development assistant, handling:

- Architecture decisions and implementation
- Complex refactoring and debugging
- Documentation and test writing
- CI/CD pipeline development

### AI Agent Security Model

The AI agents implement a comprehensive multi-layer security model with command-based control, user authorization, commit-level validation, and deterministic security processes. Key features include:

- **Keyword Triggers**: `[Action][Agent]` format (e.g., `[Approved][Claude]`)
- **Allow List**: Only pre-approved users can trigger agents
- **Commit Validation**: Prevents code injection after approval
- **Implementation Requirements**: Only complete, working code is accepted

**For complete security documentation, see** `packages/github_ai_agents/docs/security.md`

### Remote Infrastructure

**IMPORTANT**: The Gaea2 MCP server can run on a dedicated remote machine at `192.168.0.152:8007`:
- Gaea2 requires Windows with the Gaea2 software installed
- Health checks gracefully handle when the server is unavailable
- Do NOT change remote addresses to localhost in PR reviews

## Commands

### Running Tests

```bash
# Run all tests with coverage (containerized)
docker-compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml

# Run a specific test file
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v

# Run tests with specific test name pattern
docker-compose run --rm python-ci pytest -k "test_format" -v

# Quick test run using helper script (excludes gaea2 tests)
./scripts/run-ci.sh test

# Run only Gaea2 tests (requires remote server at 192.168.0.152:8007)
./scripts/run-ci.sh test-gaea2

# Run all tests including Gaea2 (gaea2 tests may fail if server unavailable)
./scripts/run-ci.sh test-all
```

**Note**: Gaea2 integration tests are separated from the main test suite because they require the remote Gaea2 MCP server to be available. In PR validation, these tests run in a separate job that checks server availability first.

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
# MODULAR MCP SERVERS (Container-First Approach)

# Start servers in Docker (recommended for consistency)
docker-compose up -d mcp-code-quality        # Port 8010 - Code formatting/linting
docker-compose up -d mcp-content-creation    # Port 8011 - Manim & LaTeX
docker-compose up -d mcp-gaea2               # Port 8007 - Terrain generation

# For local development (when actively developing server code)
python -m tools.mcp.code_quality.server      # Port 8010
python -m tools.mcp.content_creation.server  # Port 8011
python -m tools.mcp.gaea2.server             # Port 8007
python -m tools.mcp.ai_toolkit.server        # Port 8012 (bridge to remote)
python -m tools.mcp.comfyui.server           # Port 8013 (bridge to remote)

# Gemini MUST run on host (requires Docker access)
python -m tools.mcp.gemini.server            # Port 8006 - AI integration (host only)
./tools/mcp/gemini/scripts/start_server.sh --mode http

# Test all MCP servers at once
python scripts/mcp/test_all_servers.py

# Quick test of running servers
python scripts/mcp/test_all_servers.py --quick

# View logs for specific servers
docker-compose logs -f mcp-code-quality

# Test individual servers
python tools/mcp/code_quality/scripts/test_server.py
python tools/mcp/content_creation/scripts/test_server.py
python tools/mcp/gemini/scripts/test_server.py
python tools/mcp/gaea2/scripts/test_server.py
python tools/mcp/ai_toolkit/scripts/test_server.py
python tools/mcp/comfyui/scripts/test_server.py

# Run the main application
python main.py

# For local development without Docker
pip install -r requirements.txt
```

### AI Agents

```bash
# IMPORTANT: Agent Containerization Strategy
# Some agents run on host, others can be containerized
# See docs/AGENT_CONTAINERIZATION_STRATEGY.md for complete details

# Host-Only Agents (authentication constraints):
# 1. Claude CLI - requires subscription auth (machine-specific)
# 2. Gemini CLI - requires Docker socket access
# See docs/AI_AGENTS_CLAUDE_AUTH.md for Claude auth details

# Containerized Agents (OpenRouter-compatible):
# OpenCode, Crush - run in openrouter-agents container
docker-compose run --rm openrouter-agents python -m github_ai_agents.cli issue-monitor

# Or use specific containerized agents:
docker-compose run --rm openrouter-agents crush run -q "Write a Python function"

# Host agent execution (Claude, Gemini only):
python3 -m github_ai_agents.cli issue-monitor
python3 -m github_ai_agents.cli pr-monitor
# Or use the installed commands directly:
issue-monitor
pr-monitor

# GitHub Actions automatically run agents on schedule:
# - Issue Monitor: Every hour (runs on host)
# - PR Review Monitor: Every hour (runs on host)

# Installation:
# Step 1: Install the GitHub AI agents package (required for all agents):
pip3 install -e ./packages/github_ai_agents

# Step 2: If running Claude or Gemini on host, install host-specific dependencies:
pip3 install --user -r docker/requirements-agents.txt

# Note: Step 2 is only needed if you plan to use Claude or Gemini agents.
# Containerized agents (OpenCode, Crush) don't require host dependencies.
```

### Docker Operations

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f mcp-code-quality
docker-compose logs -f mcp-content-creation
docker-compose logs -f mcp-gaea2
docker-compose logs -f python-ci

# Stop services
docker-compose down

# Rebuild after changes
docker-compose build mcp-code-quality
docker-compose build mcp-content-creation
docker-compose build mcp-gaea2
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

### MCP Server Architecture (Modular Design)

The project uses a modular collection of Model Context Protocol (MCP) servers, each specialized for specific functionality:

1. **Code Quality MCP Server** (`tools/mcp/code_quality/`): HTTP API on port 8010
   - **Code Formatting & Linting**:
     - `format_check` - Check code formatting (Python, JS, TS, Go, Rust)
     - `lint` - Run static analysis with multiple linters
     - `autoformat` - Automatically format code files
   - See `tools/mcp/code_quality/docs/README.md` for documentation

2. **Content Creation MCP Server** (`tools/mcp/content_creation/`): HTTP API on port 8011
   - **Manim & LaTeX Tools**:
     - `create_manim_animation` - Create mathematical/technical animations
     - `compile_latex` - Generate PDF/DVI/PS documents from LaTeX
     - `render_tikz` - Render TikZ diagrams as standalone images
   - See `tools/mcp/content_creation/docs/README.md` for documentation

3. **Gemini MCP Server** (`tools/mcp/gemini/`): HTTP API on port 8006
   - **MUST run on host system** (not in container) due to Docker requirements
   - **AI Integration**:
     - `consult_gemini` - Get AI assistance for technical questions
     - `clear_gemini_history` - Clear conversation history for fresh responses
     - `gemini_status` - Get integration status and statistics
     - `toggle_gemini_auto_consult` - Control auto-consultation
   - See `tools/mcp/gemini/docs/README.md` for documentation

4. **Gaea2 MCP Server** (`tools/mcp/gaea2/`): HTTP API on port 8007
   - **Terrain Generation** (185 nodes supported):
     - `create_gaea2_project` - Create custom terrain projects
     - `create_gaea2_from_template` - Use professional templates
     - `validate_and_fix_workflow` - Comprehensive validation and repair
     - `analyze_workflow_patterns` - Pattern-based workflow analysis
     - `optimize_gaea2_properties` - Performance/quality optimization
     - `suggest_gaea2_nodes` - Intelligent node suggestions
     - `repair_gaea2_project` - Fix damaged project files
     - `run_gaea2_project` - CLI automation (Windows only)
   - Can run locally or on remote server (192.168.0.152:8007)
   - See `tools/mcp/gaea2/docs/README.md` for complete documentation

5. **AI Toolkit MCP Server** (`tools/mcp/ai_toolkit/`): HTTP API on port 8012
   - **LoRA Training Management**:
     - Training configurations, dataset uploads, job monitoring
     - Model export and download capabilities
   - Bridge to remote AI Toolkit instance at `192.168.0.152:8012`
   - See `tools/mcp/ai_toolkit/docs/README.md` for documentation

6. **ComfyUI MCP Server** (`tools/mcp/comfyui/`): HTTP API on port 8013
   - **AI Image Generation**:
     - Image generation with workflows
     - LoRA model management and transfer
     - Custom workflow execution
   - Bridge to remote ComfyUI instance at `192.168.0.152:8013`
   - See `tools/mcp/comfyui/docs/README.md` for documentation

7. **Shared Core Components** (`tools/mcp/core/`):
   - `BaseMCPServer` - Base class for all MCP servers
   - `HTTPBridge` - Bridge for remote MCP servers
   - Common utilities and helpers

8. **Containerized CI/CD**:
   - **Python CI Container** (`docker/python-ci.Dockerfile`): All Python tools
   - **Helper Scripts**: Centralized CI operations
   - **Individual MCP Containers**: Each server can run in its own optimized container

**For comprehensive MCP architecture documentation, see** `docs/mcp/README.md`

### GitHub Actions Integration

The repository includes comprehensive CI/CD workflows:

- **PR Validation**: Automatic Gemini AI code review with history clearing
- **Testing Pipeline**: Containerized pytest with coverage reporting
- **Code Quality**: Multi-stage linting in Docker containers
- **Self-hosted Runners**: All workflows run on self-hosted infrastructure
- **Runner Maintenance**: Automated cleanup and health checks

### Container Architecture Philosophy

1. **Everything Containerized** (with documented exceptions):
   - Python CI/CD tools run in `python-ci` container (Python 3.11)
   - MCP servers run in their own containers
   - **Exceptions due to authentication requirements**:
     - Gemini CLI (requires Docker access)
     - AI Agents using Claude CLI (requires host subscription auth - see `docs/AI_AGENTS_CLAUDE_AUTH.md`)
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

- **MCP Servers**: The project uses modular MCP servers. See `docs/mcp/README.md` for architecture details.
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

## GitHub Etiquette

**IMPORTANT**: When working with GitHub issues, PRs, and comments:

- **NEVER use @ mentions** unless referring to actual repository maintainers
- Do NOT use @Gemini, @Claude, @OpenAI, etc. - these may ping unrelated GitHub users
- Instead, refer to AI agents without the @ symbol: "Gemini", "Claude", "OpenAI"
- Only @ mention users who are:
  - The repository owner (@AndrewAltimit)
  - Active contributors listed in the repository
  - Users who have explicitly asked to be mentioned
- When referencing AI reviews, use phrases like:
  - "As noted in Gemini's review..."
  - "Addressing Claude's feedback..."
  - "Per the AI agent's suggestion..."

This prevents accidentally notifying random GitHub users who happen to share names with our AI tools.

## Additional Documentation

For detailed information on specific topics, refer to these documentation files:

### Infrastructure & Setup
- `docs/SELF_HOSTED_RUNNER_SETUP.md` - Self-hosted GitHub Actions runner configuration
- `docs/GITHUB_ENVIRONMENTS_SETUP.md` - GitHub environments and secrets setup
- `docs/CONTAINERIZED_CI.md` - Container-based CI/CD philosophy and implementation

### AI Agents & Security
- `packages/github_ai_agents/docs/security.md` - Comprehensive AI agent security documentation
- `docs/AI_AGENTS.md` - AI agent system overview
- `docs/AI_AGENTS_SECURITY.md` - Security-focused agent documentation
- `docs/AI_AGENTS_CLAUDE_AUTH.md` - Why AI agents run on host (Claude auth limitation)

### MCP Servers
- `docs/mcp/README.md` - MCP architecture and design patterns
- `docs/MCP_SERVERS.md` - Individual server documentation
- `docs/MCP_TOOLS.md` - Available MCP tools reference

### Integrations
- `docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md` - LoRA training and image generation
- `docs/LORA_TRANSFER_DOCUMENTATION.md` - LoRA model transfer between services
- `docs/GEMINI_SETUP.md` - Gemini CLI setup and configuration

### Gaea2 Terrain Generation
- `docs/gaea2/INDEX.md` - Complete Gaea2 documentation index
- `docs/gaea2/README.md` - Main Gaea2 MCP documentation
- `docs/gaea2/GAEA2_QUICK_REFERENCE.md` - Quick reference guide

## AI Toolkit & ComfyUI Integration

The AI Toolkit and ComfyUI MCP servers provide bridges to remote instances for LoRA training and image generation. Key points:

- **Dataset Paths**: Use absolute paths starting with `/ai-toolkit/datasets/`
- **Chunked Upload**: Required for files >100MB
- **FLUX Workflows**: Different from SD workflows (cfg=1.0, special nodes)

**For comprehensive integration guide, see** `docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md`

## Gaea2 MCP Integration

The Gaea2 MCP server provides comprehensive terrain generation capabilities:

- **Complete Node Support**: All 185 documented Gaea2 nodes
- **Intelligent Validation**: Automatic error correction and optimization
- **Professional Templates**: 11 ready-to-use terrain workflows
- **Windows Requirement**: Must run on Windows with Gaea2 installed

**For complete Gaea2 documentation:**
- `docs/gaea2/INDEX.md` - Documentation index
- `docs/gaea2/README.md` - Main documentation
- `docs/gaea2/GAEA2_API_REFERENCE.md` - API reference
- `docs/gaea2/GAEA2_EXAMPLES.md` - Usage examples
