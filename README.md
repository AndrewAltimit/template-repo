# MCP-Enabled Project Template

A comprehensive development ecosystem with 7 AI agents, 8 MCP servers, and complete CI/CD automation - all running on self-hosted, zero-cost infrastructure.

![MCP Demo](docs/template-repo.webp)

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
  - OpenCode MCP (port 8014)
  - Crush MCP (port 8015)
  - AI Toolkit MCP (port 8012)
  - ComfyUI MCP (port 8013)

## AI Agents

This repository leverages **seven AI agents** for development and automation:

1. **Claude Code** (Primary Development)
   - Main development assistant via claude.ai/code
   - Handles code implementation, refactoring, and documentation
   - Follows guidelines in CLAUDE.md

2. **OpenCode** (Comprehensive Code Generation)
   - Advanced code generation using Qwen 2.5 Coder model
   - Supports refactoring, review, and multi-step planning
   - Available via MCP, CLI, and GitHub triggers
   - See [OpenCode & Crush Integration](docs/OPENCODE_CRUSH_INTEGRATION.md)

3. **Crush** (Fast Code Generation)
   - Optimized for quick code snippets and conversions
   - Rapid prototyping and language translation
   - Lightweight and responsive
   - See [Quick Reference](docs/OPENCODE_CRUSH_QUICK_REFERENCE.md)

4. **Gemini CLI** (PR Code Review)
   - Automatically reviews all pull requests
   - Provides security, quality, and architecture feedback
   - Runs on self-hosted runners with project context

5. **GitHub Copilot** (Code Review)
   - Reviews code changes and suggests improvements
   - Provides inline review comments in pull requests
   - Complements Gemini's automated reviews

6. **Issue Monitor Agent** (Automated Issue Management)
   - Monitors GitHub issues for completeness
   - Automatically creates PRs from well-described issues
   - Triggered by keyword commands like `[Approved][Claude]`
   - Runs every hour via GitHub Actions

7. **PR Review Monitor Agent** (Automated Review Response)
   - Monitors PR reviews and implements requested changes
   - Uses Claude Code CLI to address feedback automatically
   - Triggered by keyword commands like `[Fix][Claude]`
   - Runs every hour or on PR review events

## Features

- **MCP Server Integration** - Multiple MCP servers for different tool categories
- **Gaea2 Terrain Generation** - MCP integration for all Gaea2 nodes
- **ComfyUI Integration** - Image generation workflows
- **AI Toolkit** - LoRA training capabilities
- **Gemini AI Consultation** - Standalone MCP server for AI assistance (host-only)
- **AI Code Review** - Automatic Gemini-powered PR reviews
- **Manim Animations** - Mathematical and technical animations
- **LaTeX Compilation** - Document generation
- **Self-Hosted Runners** - GitHub Actions with local infrastructure
- **Docker Compose** - Containerized services
- **AI-Powered Development** - Seven AI agents working in harmony
- **Automated Issue Processing** - Issues automatically converted to PRs
- **Automated Review Response** - PR feedback automatically implemented

## Quick Start

1. **Prerequisites**
   - Linux system (Ubuntu/Debian recommended)
   - Docker (v20.10+) and Docker Compose (v2.0+) installed
   - No other dependencies required!

2. **Clone and setup**

   ```bash
   git clone https://github.com/AndrewAltimit/template-repo
   cd template-repo

   # Install AI agents package (for CLI tools)
   pip3 install -e ./packages/github_ai_agents

   # Set up API keys (if using AI features)
   export OPENROUTER_API_KEY="your-key-here"  # For OpenCode/Crush
   export GEMINI_API_KEY="your-key-here"      # For Gemini
   ```

3. **Start services**

   ```bash
   # Start all MCP servers (containerized)
   docker-compose up -d

   # Or start specific servers
   docker-compose up -d mcp-code-quality mcp-content-creation
   docker-compose up -d mcp-opencode mcp-crush

   # Start Gemini MCP server (must run on host)
   python -m tools.mcp.gemini.server

   # Quick test all servers
   python scripts/mcp/test_all_servers.py --quick
   ```

4. **Use AI agents**

   ```bash
   # Interactive AI sessions
   ./tools/utilities/run_claude.sh     # Claude Code
   ./tools/utilities/run_opencode.sh   # OpenCode
   ./tools/utilities/run_crush.sh      # Crush

   # Quick code generation
   ./tools/utilities/run_opencode.sh -q "Create a REST API"
   ./tools/utilities/run_crush.sh -q "Binary search function"
   ```

5. **For CI/CD (optional)**
   - Set up a self-hosted runner following [this guide](docs/SELF_HOSTED_RUNNER_SETUP.md)
   - All CI operations run in containers - no local tool installation needed

## Project Structure

```
.
├── .github/workflows/      # GitHub Actions workflows
├── docker/                 # Docker configurations
├── packages/               # Installable packages
│   └── github_ai_agents/  # AI agent implementations
├── tools/                  # MCP servers and utilities
│   ├── mcp/               # Modular MCP servers
│   │   ├── code_quality/  # Formatting & linting (8010)
│   │   ├── content_creation/ # Manim & LaTeX (8011)
│   │   ├── gemini/        # AI consultation (8006)
│   │   ├── gaea2/         # Terrain generation (8007)
│   │   ├── opencode/      # Code generation (8014)
│   │   ├── crush/         # Fast generation (8015)
│   │   ├── ai_toolkit/    # LoRA training (8012)
│   │   └── comfyui/       # Image generation (8013)
│   └── utilities/         # Helper scripts
├── scripts/               # CI/CD and utility scripts
├── tests/                 # Test files
├── docs/                  # Documentation
├── CLAUDE.md             # Claude Code instructions
└── PROJECT_CONTEXT.md    # Context for AI reviewers
```

## MCP Tools Available

### Code Quality MCP Server (Port 8010)
- `format_check` - Check code formatting (Python, JS, TS, Go, Rust)
- `lint` - Run static analysis with multiple linters
- `autoformat` - Automatically format code files

### Content Creation MCP Server (Port 8011)
- `create_manim_animation` - Create mathematical/technical animations
- `compile_latex` - Generate PDF/DVI/PS documents from LaTeX
- `render_tikz` - Render TikZ diagrams as standalone images

**Gaea2 Terrain Generation:**
- `create_gaea2_project` - Create custom terrain projects with automatic validation
- `validate_and_fix_workflow` - Validate and repair workflows with proper ID handling
- `create_gaea2_from_template` - Use professional templates for quick terrain creation
- `analyze_workflow_patterns` - Get pattern-based suggestions from real projects
- `repair_gaea2_project` - Fix damaged project files automatically
- Plus 5 more tools - see [Gaea2 documentation](docs/gaea2/README.md)

### AI Code Generation MCP Servers

**OpenCode MCP Server (Port 8014):**
- `consult_opencode` - Generate, refactor, review, or explain code
- `clear_opencode_history` - Clear conversation history
- `opencode_status` - Get integration status and statistics
- `toggle_opencode_auto_consult` - Control auto-consultation

**Crush MCP Server (Port 8015):**
- `consult_crush` - Quick code generation and conversion
- `clear_crush_history` - Clear conversation history
- `crush_status` - Get integration status
- `toggle_crush_auto_consult` - Control auto-consultation

### Gemini MCP Server (Port 8006)

**AI Integration (Host-only):**
- `consult_gemini` - Get AI assistance
- `clear_gemini_history` - Clear conversation history
- `gemini_status` - Get integration status
- `toggle_gemini_auto_consult` - Control auto-consultation

**Note:** The Gemini MCP server must run on the host system due to Docker requirements.

### AI Toolkit MCP Server (Port 8012)
- LoRA training management
- Dataset uploads and job monitoring
- Model export and download capabilities
- Bridge to remote AI Toolkit instance

### ComfyUI MCP Server (Port 8013)
- AI image generation workflows
- LoRA model management and transfer
- Custom workflow execution
- Bridge to remote ComfyUI instance

### Remote Services Setup

- **ComfyUI workflows** - [Setup guide](https://gist.github.com/AndrewAltimit/f2a21b1a075cc8c9a151483f89e0f11e)
- **AI Toolkit LoRA training** - [Setup guide](https://gist.github.com/AndrewAltimit/2703c551eb5737de5a4c6767d3626cb8)
- **Integration Guide** - [AI Toolkit & ComfyUI Integration](docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md)

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

This project uses seven AI agents. See [AI Agents Documentation](docs/AI_AGENTS.md) for details on:

- Claude Code (primary development)
- OpenCode (comprehensive code generation) - [Integration Guide](docs/OPENCODE_CRUSH_INTEGRATION.md)
- Crush (fast code generation) - [Quick Reference](docs/OPENCODE_CRUSH_QUICK_REFERENCE.md)
- Gemini CLI (automated PR reviews)
- GitHub Copilot (code review suggestions)
- Issue Monitor Agent (automated issue management)
- PR Review Monitor Agent (automated review response)

**Security Features:**
- Keyword trigger system (e.g., `[Approved][Claude]`) prevents accidental activation
- User allow list prevents unauthorized access
- GitHub Environments for secure token management
- See [AI Agents Security](docs/AI_AGENTS_SECURITY.md) for configuration

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

## Documentation

### Quick References
- [OpenCode & Crush Quick Reference](docs/OPENCODE_CRUSH_QUICK_REFERENCE.md) - Command cheatsheet
- [MCP Tools Reference](docs/MCP_TOOLS.md) - All available MCP tools
- [CLAUDE.md](CLAUDE.md) - Project-specific Claude Code instructions

### Integration Guides
- [OpenCode & Crush Integration](docs/OPENCODE_CRUSH_INTEGRATION.md) - Complete guide for AI code generation
- [AI Toolkit & ComfyUI Integration](docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md) - LoRA training and image generation
- [Gaea2 Documentation](docs/gaea2/README.md) - Terrain generation with 185 nodes

### Setup & Configuration
- [Self-Hosted Runner Setup](docs/SELF_HOSTED_RUNNER_SETUP.md) - GitHub Actions runner configuration
- [GitHub Environments Setup](docs/GITHUB_ENVIRONMENTS_SETUP.md) - Secure token management
- [Gemini Setup](docs/GEMINI_SETUP.md) - Gemini CLI configuration
- [Containerized CI](docs/CONTAINERIZED_CI.md) - Docker-based CI/CD

### AI Agents & Security
- [AI Agents Documentation](docs/AI_AGENTS.md) - Overview of all 7 AI agents
- [AI Agents Security](docs/AI_AGENTS_SECURITY.md) - Security model and configuration
- [Agent Containerization Strategy](docs/AGENT_CONTAINERIZATION_STRATEGY.md) - Container vs host execution

### MCP Architecture
- [MCP Architecture](docs/mcp/README.md) - Modular server design patterns
- [MCP Servers](docs/MCP_SERVERS.md) - Individual server documentation

## License

This project is released under the [Unlicense](LICENSE) (public domain dedication).

**For jurisdictions that do not recognize public domain:** As a fallback, this project is also available under the [MIT License](LICENSE-MIT).
