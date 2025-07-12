# MCP-Enabled Project Template

A comprehensive template for projects using Model Context Protocol (MCP) tools with GitHub Actions self-hosted runners.

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

## Quick Start

1. **Clone this template**
   ```bash
   git clone <your-repo-url>
   cd <your-repo>
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start MCP server**
   ```bash
   docker-compose up -d mcp-server
   ```

4. **Set up self-hosted runner**
   ```bash
   ./scripts/setup-runner.sh
   ```

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
└── docs/                  # Documentation
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

All workflows run on self-hosted runners with Docker containerization for consistent environments. Python CI/CD operations run in containers to avoid dependency conflicts.

## Development

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

### Running Tests
```bash
# Using Docker Compose directly
docker-compose run --rm python-ci pytest tests/ -v

# Using the CI script
./scripts/run-ci.sh test
```
