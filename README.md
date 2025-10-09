# MCP-Enabled Project Template

A comprehensive development ecosystem with 6 AI agents, 14 MCP servers, and complete CI/CD automation - all running on self-hosted, zero-cost infrastructure.

![MCP Demo](docs/mcp/architecture/demo.gif)

## Project Philosophy

This project follows a **container-first approach**:

- **All tools and CI/CD operations run in Docker containers** for maximum portability
- **Zero external dependencies** - runs on any Linux system with Docker
- **Self-hosted infrastructure** - no cloud costs, full control over runners
- **Single maintainer design** - optimized for individual developer productivity
- **Modular MCP architecture** - Separate specialized servers for different functionalities

## AI Agents

Six AI agents working in harmony for development and automation. See [AI Agents Documentation](docs/ai-agents/README.md) for complete details:

1. **Claude Code** - Primary development assistant
2. **Codex** - AI-powered code generation and completion ([Setup Guide](docs/ai-agents/codex-setup.md))
3. **OpenCode** - Comprehensive code generation ([Integration Guide](docs/integrations/ai-services/opencode-crush.md))
4. **Crush** - Fast code generation ([Quick Reference](docs/integrations/ai-services/opencode-crush-ref.md))
5. **Gemini CLI** - Interactive development & automated PR reviews
6. **GitHub Copilot** - Code review suggestions

**Security**: Keyword triggers, user allow list, secure token management. See [AI Agents Security](docs/ai-agents/security.md)

**Safety Training**: Essential AI safety concepts for human-AI collaboration. See [Human Training Guide](docs/ai-agents/human-training.md)

**Sleeper Detection**: Advanced AI agent backdoor and sleeper detection system. See [Sleeper Detection Package](packages/sleeper_detection/README.md)

## Features

- **14 MCP Servers** - Modular tools for code quality, content creation, AI assistance, 3D graphics, video editing, speech synthesis, virtual characters, and more
- **6 AI Agents** - Comprehensive development automation
- **Sleeper Detection System** - Advanced AI backdoor detection using TransformerLens residual stream analysis
- **Company Integration** - Custom agent builds for corporate AI APIs ([Documentation](automation/corporate-proxy/shared/docs/ARCHITECTURE.md))
- **Video Editor** - AI-powered video editing with transcription, speaker diarization, and intelligent scene detection
- **Gaea2 Terrain Generation** - Professional terrain generation
- **Blender 3D Creation** - Full 3D content creation, rendering, and simulation
- **ComfyUI & AI Toolkit** - Image generation and LoRA training
- **Container-First Architecture** - Maximum portability and consistency
- **Self-Hosted CI/CD** - Zero-cost GitHub Actions infrastructure
- **Automated PR Workflows** - AI-powered reviews and fixes

## Quick Start

> **New to the template?** Check out our **[Template Quickstart Guide](docs/QUICKSTART.md)** for step-by-step customization instructions!
> - Choose from 4 pre-configured paths (Minimal, AI-Powered, Content Creation, Full Stack)
> - Learn what to enable/disable for your specific use case
> - Get up and running in 15 minutes

1. **Prerequisites**
   - Linux system (Ubuntu/Debian recommended)
   - Docker (v20.10+) and Docker Compose (v2.0+)
   - No other dependencies required!

2. **Clone and setup**
   ```bash
   git clone https://github.com/AndrewAltimit/template-repo
   cd template-repo

   # Install AI agents package (for CLI tools)
   pip3 install -e ./packages/github_ai_agents

   # Set up API keys (if using AI features)
   export OPENROUTER_API_KEY="your-key-here"  # For OpenCode/Crush
   export GEMINI_API_KEY="your-key-here"      # For Gemini (dont use API key for free tier, use web auth)
   # For Codex: run 'codex auth' after installing @openai/codex
   ```

3. **Use MCP servers with Claude Code and other agents**
   - **Essential MCP servers** are configured in `.mcp.json` (code-quality, AI agents)
   - **All MCP servers** including specialized tools are in `.mcp.json.full` (content creation, 3D graphics, etc.)
   - Use `.mcp.json` by default to avoid context window overload
   - Rename `.mcp.json.full` to `.mcp.json` to enable all specialized services
   - No manual startup required! Agents can start the services themselves.

4. **For standalone usage**
   ```bash
   # Start HTTP servers for testing/development
   docker-compose up -d

   # Test all servers
   python automation/testing/test_all_servers.py --quick

   # Use AI agents directly
   ./tools/cli/agents/run_codex.sh    # Interactive Codex session
   ./tools/cli/agents/run_opencode.sh -q "Create a REST API"
   ./tools/cli/agents/run_crush.sh -q "Binary search function"
   ./tools/cli/agents/run_gemini.sh   # Interactive Gemini CLI session
   ```

For detailed setup instructions, see [CLAUDE.md](CLAUDE.md)

## MCP Configuration Strategy

This repository provides two MCP configuration files to optimize performance:

### `.mcp.json` (Default - Essential Services)
- **Purpose**: Prevent context window overload in Claude Code
- **Contains**: Essential services only
  - Code Quality (formatting, linting)
  - AI Agents (Gemini, OpenCode, Crush, Codex)
- **Best for**: Day-to-day development, code review, refactoring
- **Use when**: Working on typical software development tasks

### `.mcp.json.full` (Complete - All Services)
- **Purpose**: Access to all specialized tools when needed
- **Contains**: All 14 MCP servers
  - Essential services (from `.mcp.json`)
  - Content creation (Manim, LaTeX, TikZ)
  - 3D graphics (Blender, Gaea2)
  - Media tools (Video Editor, Speech Synthesis, Meme Generator)
  - Remote services (AI Toolkit, ComfyUI, Virtual Character)
- **Best for**: Specialized tasks requiring content creation or media processing
- **Use when**: Creating animations, 3D content, videos, or terrain

### Switching Between Configurations

```bash
# Use essential services (default)
# Already configured - just use Claude Code normally

# Enable all services temporarily
mv .mcp.json .mcp.json.essential
mv .mcp.json.full .mcp.json
# Restart Claude Code

# Restore essential services
mv .mcp.json .mcp.json.full
mv .mcp.json.essential .mcp.json
# Restart Claude Code
```

**Recommendation**: Start with `.mcp.json` (essential services) and only switch to `.mcp.json.full` when you need specialized tools. This prevents Claude's context window from being filled with unused tool definitions.

## Enterprise & Corporate Setup

### Corporate Certificate Installation

For enterprise environments that require custom certificates (e.g., corporate proxy certificates, self-signed certificates), we provide a standardized installation mechanism:

1. **Certificate Installation Script**: [`automation/corporate-proxy/shared/scripts/install-corporate-certs.sh`](automation/corporate-proxy/shared/scripts/install-corporate-certs.sh)
   - Placeholder script that organizations can customize with their certificate installation process
   - Automatically executed during Docker image builds for all corporate proxy containers

2. **Customization Guide**: See [`automation/corporate-proxy/shared/scripts/README.md`](automation/corporate-proxy/shared/scripts/README.md) for:
   - Step-by-step instructions on customizing the certificate installation
   - Examples for different certificate formats and installation methods
   - Best practices for certificate management in containerized environments

3. **Affected Services**:
   - All corporate proxy integrations (Gemini, Codex, OpenCode, Crush)
   - Python CI/CD containers
   - Any custom Docker images built from this template

This pattern ensures consistent certificate handling across all services while maintaining security and flexibility for different corporate environments.

## Project Structure

```
.
├── .github/workflows/        # GitHub Actions workflows
├── docker/                   # Docker configurations
├── packages/                 # Installable packages
│   ├── github_ai_agents/     # AI agent implementations
│   └── sleeper_detection/    # AI backdoor detection system
├── tools/                    # MCP servers and utilities
│   ├── mcp/                  # Modular MCP servers
│   │   ├── code_quality/     # Formatting & linting
│   │   ├── content_creation/ # Manim & LaTeX
│   │   ├── gemini/           # AI consultation
│   │   ├── gaea2/            # Terrain generation
│   │   ├── blender/          # 3D content creation
│   │   ├── codex/            # AI-powered code generation
│   │   ├── opencode/         # Code generation
│   │   ├── crush/            # Code generation
│   │   ├── video_editor/     # AI-powered video editing
│   │   ├── meme_generator/   # Meme creation
│   │   ├── elevenlabs_speech/# Speech synthesis
│   │   ├── virtual_character/# AI agent embodiment
│   │   ├── ai_toolkit/       # LoRA training interface
│   │   ├── comfyui/          # Image generation interface
│   │   └── core/             # Shared components
│   └── cli/                  # Command-line tools
│       ├── agents/           # Agent runner scripts
│       │   ├── run_claude.sh              # Claude Code Runner
│       │   ├── run_codex.sh               # Codex runner
│       │   ├── run_opencode.sh            # OpenCode runner
│       │   ├── run_crush.sh               # Crush runner
│       │   └── run_gemini.sh              # Gemini CLI runner
│       ├── containers/       # Container runner scripts
│       │   ├── run_codex_container.sh     # Codex in container
│       │   ├── run_opencode_container.sh  # OpenCode in container
│       │   ├── run_crush_container.sh     # Crush in container
│       │   └── run_gemini_container.sh    # Gemini in container
│       └── utilities/        # Other CLI utilities
├── automation/               # CI/CD and automation scripts
│   ├── analysis/             # Code and project analysis tools
│   ├── ci-cd/                # CI/CD pipeline scripts
│   ├── corporate-proxy/      # Corporate proxy integrations
│   │   ├── gemini/           # Gemini CLI proxy wrapper
│   │   ├── codex/            # Codex proxy wrapper
│   │   ├── opencode/         # OpenCode proxy wrapper
│   │   ├── crush/            # Crush proxy wrapper
│   │   └── shared/           # Shared proxy components
│   ├── launchers/            # Service launcher scripts
│   ├── monitoring/           # Service and PR monitoring
│   ├── review/               # Code review automation
│   ├── scripts/              # Utility scripts
│   ├── security/             # Security and validation
│   ├── setup/                # Setup and installation scripts
│   └── testing/              # Testing utilities
├── tests/                    # Test files
├── docs/                     # Documentation
├── config/                   # Configuration files
```

## MCP Servers

### Available Servers

1. **Code Quality** - Formatting, linting, auto-formatting
2. **Content Creation** - Manim animations, LaTeX, TikZ diagrams
3. **Gaea2** - Terrain generation ([Documentation](tools/mcp/gaea2/docs/README.md))
4. **Blender** - 3D content creation, rendering, physics simulation ([Documentation](tools/mcp/blender/docs/README.md))
5. **Gemini** - AI consultation (containerized and host modes available)
6. **Codex** - AI-powered code generation and completion
7. **OpenCode** - Comprehensive code generation
8. **Crush** - Fast code snippets
9. **Meme Generator** - Create memes with templates
10. **ElevenLabs Speech** - Advanced TTS with v3 model, 50+ audio tags, 74 languages ([Documentation](tools/mcp/elevenlabs_speech/docs/README.md))
11. **Video Editor** - AI-powered video editing with transcription and scene detection ([Documentation](tools/mcp/video_editor/docs/README.md))
12. **Virtual Character** - AI agent embodiment in virtual worlds (VRChat, Blender, Unity) ([Documentation](tools/mcp/virtual_character/README.md))
13. **AI Toolkit** - LoRA training interface (remote: 192.168.0.152:8012)
14. **ComfyUI** - Image generation interface (remote: 192.168.0.152:8013)

### Usage Modes

- **STDIO Mode** (local MCPs): Configured in `.mcp.json`, auto-started by Claude
- **HTTP Mode** (remote MCPs): Run the MCP using docker-compose on the remote node.

See [MCP Architecture Documentation](docs/mcp/README.md) and [STDIO vs HTTP Modes](docs/mcp/architecture/stdio-vs-http.md) for details.

### Tool Reference

For complete tool listings, see [MCP Tools Reference](docs/mcp/tools.md)

## Configuration

### Environment Variables

See `.env.example` for all available options.

### Key Configuration Files

- `.mcp.json` - MCP server configuration for Claude Code
- `docker-compose.yml` - Container services configuration
- `CLAUDE.md` - Project-specific Claude Code instructions (root directory)
- `CRUSH.md` - Crush AI assistant instructions (root directory)
- `AGENTS.md` - Universal AI agent configuration and guidelines (root directory)
- `docs/ai-agents/project-context.md` - Context for AI reviewers

### Setup Guides

- [Self-Hosted Runner Setup](docs/infrastructure/self-hosted-runner.md)
- [GitHub Environments Setup](docs/infrastructure/github-environments.md)
- [Gemini Setup](docs/integrations/ai-services/gemini-setup.md)
- [Containerized CI](docs/infrastructure/containerization.md)

## Development Workflow

### Container-First Development

All Python operations run in Docker containers:

```bash
# Run CI operations
./automation/ci-cd/run-ci.sh format      # Check formatting
./automation/ci-cd/run-ci.sh lint-basic  # Basic linting
./automation/ci-cd/run-ci.sh test        # Run tests
./automation/ci-cd/run-ci.sh full        # Full CI pipeline

# Run specific tests
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v
```

### GitHub Actions

- **Pull Request Validation** - Automatic Gemini AI review
- **Continuous Integration** - Full CI pipeline
- **Code Quality** - Multi-stage linting (containerized)
- **Automated Testing** - Unit and integration tests
- **Security Scanning** - Bandit and safety checks

All workflows run on self-hosted runners for zero-cost operation.

## Documentation

### Core Documentation
- [AGENTS.md](AGENTS.md) - Universal AI agent configuration and guidelines
- [CLAUDE.md](CLAUDE.md) - Claude-specific instructions and commands
- [CRUSH.md](CRUSH.md) - Crush AI assistant instructions
- [MCP Architecture](docs/mcp/README.md) - Modular server design
- [AI Agents Documentation](docs/ai-agents/README.md) - Seven AI agents overview

### Quick References
- [Codex Setup Guide](docs/ai-agents/codex-setup.md)
- [OpenCode & Crush Quick Reference](docs/integrations/ai-services/opencode-crush-ref.md)
- [MCP Tools Reference](docs/mcp/tools.md)
- [Gaea2 Quick Reference](tools/mcp/gaea2/docs/GAEA2_QUICK_REFERENCE.md)

### Integration Guides
- [Codex Integration](docs/ai-agents/codex-setup.md)
- [OpenCode & Crush Integration](docs/integrations/ai-services/opencode-crush.md)
- [AI Toolkit & ComfyUI Integration](docs/integrations/creative-tools/ai-toolkit-comfyui.md)
- [Gaea2 Documentation](tools/mcp/gaea2/docs/README.md)

### Setup & Configuration
- **[Template Quickstart Guide](docs/QUICKSTART.md)** - Customize the template for your needs
- [Self-Hosted Runner Setup](docs/infrastructure/self-hosted-runner.md)
- [GitHub Environments Setup](docs/infrastructure/github-environments.md)
- [Containerized CI](docs/infrastructure/containerization.md)

## License

This project is released under the [Unlicense](LICENSE) (public domain dedication).

**For jurisdictions that do not recognize public domain:** As a fallback, this project is also available under the [MIT License](LICENSE-MIT).
