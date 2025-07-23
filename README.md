# MCP-Enabled Project Template

A container-first, self-hosted project template using Model Context Protocol (MCP) tools with zero-cost infrastructure.

## Project Philosophy

This project follows a **container-first approach**:

- **All Python tools and CI/CD operations run in Docker containers** for maximum portability
- **MCP tools are containerized** except where Docker-in-Docker would be required (e.g., Gemini CLI)
- **Zero external dependencies** - runs on any Linux system with Docker
- **Self-hosted infrastructure** - no cloud costs, full control over runners
- **Single maintainer design** - optimized for individual developer productivity
- **Modular MCP architecture** - Separate specialized servers for different functionalities:
  - Code Quality MCP (port 8010)
  - Content Creation MCP (port 8011)
  - Gaea2 MCP (port 8007)
  - Gemini MCP (port 8006, host-only)

## AI Agents

This repository leverages **three AI agents** for development and automation:

1. **Claude Code** (Primary Development)
   - Main development assistant via claude.ai/code
   - Handles code implementation, refactoring, and documentation
   - Follows guidelines in CLAUDE.md

2. **Gemini CLI** (PR Code Review)
   - Automatically reviews all pull requests
   - Provides security, quality, and architecture feedback
   - Runs on self-hosted runners with project context

3. **GitHub Copilot** (Code Review)
   - Reviews code changes and suggests improvements
   - Provides inline review comments in pull requests
   - Complements Gemini's automated reviews

## Features

- **MCP Server Integration** - Multiple MCP servers for different tool categories
- **Gaea2 Terrain Generation** - ✅ Fully working MCP integration for all 185 Gaea2 nodes
  - Standalone Gaea2 MCP server with CLI automation and intelligent validation
  - Automatic terrain file generation with proper ID formatting (Windows host-only)
- **ComfyUI Integration** - Image generation workflows
- **AI Toolkit** - LoRA training capabilities
- **Gemini AI Consultation** - Standalone MCP server for AI assistance (host-only)
- **AI Code Review** - Automatic Gemini-powered PR reviews
- **Manim Animations** - Mathematical and technical animations
- **LaTeX Compilation** - Document generation
- **Self-Hosted Runners** - GitHub Actions with local infrastructure
- **Docker Compose** - Containerized services
- **AI-Powered Development** - Three AI agents working in harmony

## Quick Start

1. **Prerequisites**
   - Linux system (Ubuntu/Debian recommended)
   - Docker (v20.10+) and Docker Compose (v2.0+) installed
   - No other dependencies required!

2. **Clone and start**

   ```bash
   git clone https://github.com/AndrewAltimit/template-repo
   cd template-repo

   # Start main MCP server (containerized)
   docker-compose up -d mcp-server

   # Start Gemini MCP server (must run on host)
   python -m tools.mcp.gemini.server
   ```

3. **For CI/CD (optional)**
   - Set up a self-hosted runner following [this guide](docs/SELF_HOSTED_RUNNER_SETUP.md)
   - All CI operations run in containers - no local tool installation needed

## Project Structure

```
.
├── .github/workflows/      # GitHub Actions workflows
├── docker/                 # Docker configurations
├── tools/                  # MCP and other tools
│   ├── mcp/               # MCP server and tools
│   └── gemini/            # Gemini AI integration
├── scripts/               # Utility scripts
├── examples/              # Example usage
├── tests/                 # Test files
├── docs/                  # Documentation
└── PROJECT_CONTEXT.md     # Context for AI code reviewers
```

## MCP Tools Available

### Main MCP Server (Port 8005)

**Code Quality:**
- `format_check` - Check code formatting
- `lint` - Run linting

**Content Creation:**
- `create_manim_animation` - Create animations
- `compile_latex` - Generate documents

**Gaea2 Terrain Generation (Fully Working):**
- `create_gaea2_project` - Create custom terrain projects with automatic validation
- `validate_and_fix_workflow` - Validate and repair workflows with proper ID handling
- `create_gaea2_from_template` - Use professional templates for quick terrain creation
- `analyze_workflow_patterns` - Get pattern-based suggestions from real projects
- `repair_gaea2_project` - Fix damaged project files automatically
- Plus 5 more tools - see [Gaea2 documentation](docs/gaea2/README.md)

### Gemini MCP Server (Port 8006)

**AI Integration (Host-only):**
- `consult_gemini` - Get AI assistance
- `clear_gemini_history` - Clear conversation history

**Note:** The Gemini MCP server must run on the host system due to Docker requirements.

### Remote Services

- **ComfyUI workflows** - [Setup guide](https://gist.github.com/AndrewAltimit/f2a21b1a075cc8c9a151483f89e0f11e)
- **AI Toolkit LoRA training** - [Setup guide](https://gist.github.com/AndrewAltimit/2703c551eb5737de5a4c6767d3626cb8)

## Configuration

### Environment Variables

See `.env.example` for all available options:

- `GITHUB_TOKEN` - GitHub access token
- `COMFYUI_SERVER_URL` - ComfyUI server endpoint
- `AI_TOOLKIT_SERVER_URL` - AI Toolkit server endpoint

### Host-Only MCP Servers

Some MCP servers must run on the host system (not in containers):

1. **Gemini MCP Server** (port 8006) - AI development assistance:
   ```bash
   # Needs Docker access for Gemini CLI
   python -m tools.mcp.gemini.server
   # Or use HTTP mode for testing:
   python -m tools.mcp.gemini.server --mode http
   ```

2. **Gaea2 MCP Server** (port 8007) - Terrain generation with CLI automation:
   ```bash
   # Windows only - needs Gaea2 installed
   set GAEA2_PATH=C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe
   python tools/mcp/gaea2_mcp_server.py
   ```
   See [Gaea2 MCP Server docs](docs/gaea2/GAEA2_MCP_SERVER.md) for details.

### Gemini CLI Setup

For automated PR reviews:
- Install Node.js 18+ (recommended: 22.16.0)
- Install Gemini CLI: `npm install -g @google/gemini-cli`
- Authenticate: Run `gemini` command once

See [setup guide](docs/GEMINI_SETUP.md) for details.

### AI Agents Configuration

This project uses three AI agents. See [AI Agents Documentation](docs/AI_AGENTS.md) for details on:

- Claude Code (primary development)
- Gemini CLI (automated PR reviews)
- GitHub Copilot (code review suggestions)

### MCP Configuration

Edit `.mcp.json` to customize available tools and their settings.

### CI/CD Configuration

All Python CI/CD operations run in Docker containers. See [Containerized CI Documentation](docs/CONTAINERIZED_CI.md) for details.

## GitHub Actions

This template includes workflows for:

- **Pull Request Validation** - Automatic code review with Gemini AI (with history clearing)
- **Continuous Integration** - Full CI pipeline on main branch
- **Code Quality Checks** - Multi-stage linting and formatting (containerized)
- **Automated Testing** - Unit and integration tests with coverage reporting
- **Runner Maintenance** - Automated cleanup and health checks
- **Security Scanning** - Bandit and safety checks for Python dependencies

All workflows run on self-hosted runners maintained by @AndrewAltimit. The infrastructure is designed for zero-cost operation while maintaining professional CI/CD capabilities.

## Container-First Development

This project is designed to be **fully portable** using containers:

- **Python 3.11** environment in all CI/CD containers
- **All dependencies pre-installed** in the python-ci image
- **User permission handling** to avoid file ownership issues

### CI/CD Operations

All Python CI/CD operations are containerized. Use the helper scripts:

```bash
# Run formatting checks
./scripts/run-ci.sh format

# Run linting
./scripts/run-ci.sh lint-basic

# Run tests
./scripts/run-ci.sh test

# Auto-format code
./scripts/run-ci.sh autoformat

# Full CI pipeline
./scripts/run-ci.sh full
```

### Why Containers?

- **Zero setup** - No need to install Python, linters, or any tools locally
- **Consistency** - Same environment on every machine
- **Isolation** - No conflicts with system packages
- **Portability** - Works on any Linux system with Docker

### Running Tests

```bash
# Everything runs in containers - no local Python needed!
./scripts/run-ci.sh test

# Run specific test files
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v

# Run with coverage report
docker-compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml
```

### Local Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Run any Python command in the CI container
docker-compose run --rm python-ci python --version
```
