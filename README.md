# MCP-Enabled Project Template

A container-first, self-hosted project template using Model Context Protocol (MCP) tools with zero-cost infrastructure.

## Project Philosophy

This project follows a **container-first approach**:
- **All Python tools and CI/CD operations run in Docker containers** for maximum portability
- **MCP tools are containerized** except where Docker-in-Docker would be required (e.g., Gemini CLI)
- **Zero external dependencies** - runs on any Linux system with Docker
- **Self-hosted infrastructure** - no cloud costs, full control over runners
- **Single maintainer design** - optimized for individual developer productivity

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

- **MCP Server Integration** - Local MCP server with multiple tool categories
- **ComfyUI Integration** - Image generation workflows
- **AI Toolkit** - LoRA training capabilities
- **Gemini AI Consultation** - Second opinions and technical assistance
- **AI Code Review** - Automatic Gemini-powered PR reviews
- **Manim Animations** - Mathematical and technical animations
- **LaTeX Compilation** - Document generation
- **Self-Hosted Runners** - GitHub Actions with local infrastructure
- **Docker Compose** - Containerized services
- **AI-Powered Development** - Three AI agents working in harmony

## Quick Start

1. **Prerequisites**
   - Linux system (Ubuntu/Debian recommended)
   - Docker and Docker Compose installed
   - No other dependencies required!

2. **Clone and start**
   ```bash
   git clone https://github.com/AndrewAltimit/template-repo
   cd template-repo
   docker-compose up -d
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

### Code Quality
- `format_check` - Check code formatting
- `lint` - Run linting  
- `analyze` - Static analysis
- `full_ci` - Complete CI pipeline

### AI Integration
- `consult_gemini` - Get AI assistance
- `clear_gemini_history` - Clear conversation history
- `create_manim_animation` - Create animations
- `compile_latex` - Generate documents

### Remote Services
- ComfyUI workflows
- AI Toolkit LoRA training

## Configuration

### Environment Variables

See `.env.example` for all available options:
- `GITHUB_TOKEN` - GitHub access token
- `COMFYUI_SERVER_URL` - ComfyUI server endpoint
- `AI_TOOLKIT_SERVER_URL` - AI Toolkit server endpoint

### Gemini AI Setup

For AI code review on pull requests:
1. Install Node.js 18+ (recommended: 22.16.0)
2. Install Gemini CLI: `npm install -g @google/gemini-cli`
3. Authenticate: Run `gemini` command once

See [setup guide](docs/GEMINI_SETUP.md) for details.

### AI Agents Configuration

This project uses three AI agents. See [AI Agents Documentation](docs/AI_AGENTS.md) for details on:
- Claude Code (primary development)
- Gemini CLI (automated PR reviews)
- GitHub Copilot (code review suggestions)

### MCP Configuration

Edit `mcp-config.json` to customize available tools and their settings.

### CI/CD Configuration

All Python CI/CD operations run in Docker containers. See [Containerized CI Documentation](docs/CONTAINERIZED_CI.md) for details.

## GitHub Actions

This template includes workflows for:
- **Pull Request Validation** - Automatic code review with Gemini AI
- **Continuous Integration** - Full CI pipeline on main branch  
- **Code Quality Checks** - Linting and formatting (containerized)
- **Automated Testing** - Unit and integration tests
- **Runner Maintenance** - Automated cleanup and health checks

All workflows run on self-hosted runners maintained by @AndrewAltimit. The infrastructure is designed for zero-cost operation while maintaining professional CI/CD capabilities.

## Container-First Development

This project is designed to be **fully portable** using containers:

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
