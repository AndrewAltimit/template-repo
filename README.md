# MCP-Enabled Project Template

A comprehensive development ecosystem with 6 AI agents, 18 MCP servers, and complete CI/CD automation - all running on self-hosted, zero-cost infrastructure.

![MCP Demo](docs/mcp/architecture/demo.gif)

---

> **Important: This is an advanced template repository** designed for experienced developers working with autonomous AI agents. Before diving in, we strongly recommend:
>
> 1. **Read the [AI Safety Training Guide](docs/agents/human-training.md)** - Essential concepts for safe human-AI collaboration, including deception detection, scalable oversight, and control protocols
>
> 2. **Take an AI Safety course at [BlueDot Impact](https://bluedot.org/)** - Free, rigorous training programs covering AI safety fundamentals, governance, and alignment. Highly recommended for anyone building with autonomous agents.
>
> Working with AI agents introduces risks that differ fundamentally from traditional software. Understanding these risks isn't optional - it's a prerequisite for responsible development.

---

## Project Philosophy

This project follows a **container-first approach**:

- **All tools and CI/CD operations run in Docker containers** for maximum portability
- **Zero external dependencies** - runs on any Linux system with Docker
- **Self-hosted infrastructure** - no cloud costs, full control over runners
- **Single maintainer design** - optimized for individual developer productivity
- **Modular MCP architecture** - Separate specialized servers for different functionalities

## AI Agents

Six AI agents for development and automation. See [AI Agents Documentation](docs/agents/README.md) for details.

| Agent | Provider | Use Case | Documentation |
|-------|----------|----------|---------------|
| **Claude Code** | Anthropic | Primary development assistant | [Setup Guide](docs/agents/claude-code-setup.md) |
| **Codex** | OpenAI | Code generation | [Setup Guide](docs/agents/codex-setup.md) |
| **OpenCode** | OpenRouter | Code generation | [AI Code Agents](docs/integrations/ai-services/ai-code-agents.md) |
| **Crush** | OpenRouter | Code generation | [AI Code Agents](docs/integrations/ai-services/ai-code-agents.md) |
| **Gemini** | Google | Code review (limited tool use) | [Setup Guide](docs/integrations/ai-services/gemini-setup.md) |
| **GitHub Copilot** | GitHub | PR review suggestions | - |

All code generation agents (Codex, OpenCode, Crush) provide equivalent functionality - choose based on your API access.

**Security**: Keyword triggers, user allow list, secure token management. See [Security Model](packages/github_agents/docs/security.md)

**Safety Training**: Essential AI safety concepts for human-AI collaboration. See [Human Training Guide](docs/agents/human-training.md)

**Sleeper Agents**: Create and evaluate sleeper agents in order to detect misalignment and probe for deception. See [Sleeper Agents Package](packages/sleeper_agents/README.md)

## Reports & Research

Technical reports and guides exploring AI risks, safety frameworks, and philosophical questions. PDFs are automatically built from LaTeX source and published with each release.

### Emerging Technology Risk Assessments

Scenario-based projection reports analyzing potential futures involving advanced AI systems. See [Projections Documentation](docs/projections/README.md).

| Report | Topic | PDF | Source |
|--------|-------|-----|--------|
| **AI Agents Political Targeting** | Political violence risk | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/projections/latex/ai-agents-political-targeting.tex) |
| **AI Agents WMD Proliferation** | WMD proliferation risk | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/projections/latex/ai-agents-wmd-proliferation.tex) |
| **AI Agents Espionage Operations** | Intelligence tradecraft | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/projections/latex/ai-agents-espionage-operations.tex) |
| **AI Agents Economic Actors** | Autonomous economic actors | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/projections/latex/ai-agents-economic-actors.tex) |
| **AI Agents Financial Integrity** | Money laundering & corruption | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/projections/latex/ai-agents-financial-integrity.tex) |
| **AI Agents Institutional Erosion** | IC monopoly erosion & verification pivot | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/projections/latex/ai-agents-institutional-erosion.tex) |

### Technical Guides

| Guide | Description | PDF | Source |
|-------|-------------|-----|--------|
| **Sleeper Agents Framework** | AI backdoor detection using residual stream analysis | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](packages/sleeper_agents/docs/Sleeper_Agents_Framework_Guide.tex) |
| **AgentCore Memory Integration** | Multi-provider AI memory system | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/integrations/ai-services/AgentCore_Memory_Integration_Guide.tex) |
| **Virtual Character System** | AI agent embodiment platform | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/integrations/ai-services/Virtual_Character_System_Guide.tex) |

### Philosophy Papers

Philosophical explorations of minds, experience, and intelligence. See [Philosophy Papers Documentation](docs/philosophy/README.md).

| Paper | Topic | PDF | Source |
|-------|-------|-----|--------|
| **Architectural Qualia** | What Is It Like to Be an LLM? | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/philosophy/latex/architectural-qualia.tex) |

**Build Status**: [![Build Documentation](https://github.com/AndrewAltimit/template-repo/actions/workflows/build-docs.yml/badge.svg)](https://github.com/AndrewAltimit/template-repo/actions/workflows/build-docs.yml)

## Packages

Three standalone Python packages addressing different aspects of AI agent development and safety:

| Package | Purpose | Documentation |
|---------|---------|---------------|
| **[GitHub Agents](packages/github_agents/)** | Multi-agent orchestration for autonomous GitHub workflows - issue monitoring, PR review processing, and board coordination with Claude, Codex, OpenCode, Gemini, and Crush | [README](packages/github_agents/README.md) \| [Security](packages/github_agents/docs/security.md) |
| **[Sleeper Agents](packages/sleeper_agents/)** | Production-validated detection framework for hidden backdoors in LLMs, based on Anthropic's research on deceptive AI that persists through safety training | [README](packages/sleeper_agents/README.md) \| [PDF Guide](https://github.com/AndrewAltimit/template-repo/releases/latest) |
| **[Economic Agents](packages/economic_agents/)** | Simulation framework demonstrating autonomous AI economic capability - agents that earn money, form companies, hire sub-agents, and seek investment. For governance research and policy development | [README](packages/economic_agents/README.md) |

```bash
# Install all packages
pip install -e ./packages/github_agents
pip install -e ./packages/sleeper_agents
pip install -e ./packages/economic_agents
```

## Features

- **18 MCP Servers** - Modular tools for code quality, content creation, AI assistance, 3D graphics, video editing, speech synthesis, virtual characters, desktop automation, project management, and more
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
   pip3 install -e ./packages/github_agents

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
- **Contains**: All 18 MCP servers
  - Essential services (from `.mcp.json`)
  - Content creation (Manim, LaTeX, TikZ)
  - 3D graphics (Blender, Gaea2)
  - Media tools (Video Editor, Speech Synthesis, Meme Generator)
  - Remote services (AI Toolkit, ComfyUI, Virtual Character)
  - Project management (GitHub Board)
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
│   ├── github_agents/        # Github agents implementation
│   ├── sleeper_agents/       # Sleeper agents implementation
│   └── economic_agents/      # Economic agents framework
├── tools/                    # MCP servers and utilities
│   ├── mcp/                  # Modular MCP servers
│   │   ├── mcp_agentcore_memory/ # Multi-provider AI memory
│   │   ├── mcp_ai_toolkit/       # LoRA training interface
│   │   ├── mcp_blender/          # 3D content creation
│   │   ├── mcp_code_quality/     # Formatting & linting
│   │   ├── mcp_codex/            # Agent2Agent Consultation (Codex CLI)
│   │   ├── mcp_comfyui/          # Image generation interface
│   │   ├── mcp_content_creation/ # Manim & LaTeX
│   │   ├── mcp_core/             # Shared components
│   │   ├── mcp_crush/            # Agent2Agent Consultation (Crush)
│   │   ├── mcp_desktop_control/  # Desktop automation (Linux/Windows)
│   │   ├── mcp_elevenlabs_speech/# Speech synthesis
│   │   ├── mcp_gaea2/            # Terrain generation
│   │   ├── mcp_gemini/           # Agent2Agent Consultation (Gemini CLI)
│   │   ├── mcp_github_board/     # GitHub Projects board management
│   │   ├── mcp_meme_generator/   # Meme creation
│   │   ├── mcp_opencode/         # Agent2Agent Consultation (OpenCode)
│   │   ├── mcp_reaction_search/  # Semantic reaction image search
│   │   ├── mcp_video_editor/     # Video editing
│   │   └── mcp_virtual_character/# AI agent embodiment
│   └── cli/                  # Command-line tools
│       ├── agents/           # Agent runner scripts
│       │   ├── run_claude.sh       # Claude Code runner
│       │   ├── run_codex.sh        # Codex runner
│       │   ├── run_crush.sh        # Crush runner
│       │   ├── run_gemini.sh       # Gemini CLI runner
│       │   ├── run_opencode.sh     # OpenCode runner
│       │   └── stop_claude.sh      # Claude stop script
│       ├── containers/       # Container runner scripts
│       │   ├── run_codex_container.sh     # Codex in container
│       │   ├── run_crush_container.sh     # Crush in container
│       │   ├── run_gemini_container.sh    # Gemini in container
│       │   ├── run_opencode_container.sh  # OpenCode in container
│       │   └── run_opencode_simple.sh     # Simple OpenCode runner
│       └── utilities/        # Other CLI utilities
├── automation/               # CI/CD and automation scripts
│   ├── analysis/             # Code and project analysis tools
│   ├── ci-cd/                # CI/CD pipeline scripts
│   ├── corporate-proxy/      # Corporate proxy integrations
│   │   ├── crush/            # Crush proxy wrapper
│   │   ├── gemini/           # Gemini CLI proxy wrapper
│   │   ├── opencode/         # OpenCode proxy wrapper
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
3. **Gaea2** - Terrain generation ([Documentation](tools/mcp/mcp_gaea2/docs/README.md))
4. **Blender** - 3D content creation, rendering, physics simulation ([Documentation](tools/mcp/mcp_blender/docs/README.md))
5. **Gemini** - AI consultation (containerized and host modes available)
6. **Codex** - AI-powered code generation and completion
7. **OpenCode** - Code generation via OpenRouter
8. **Crush** - Code generation via OpenRouter
9. **Meme Generator** - Create memes with templates
10. **ElevenLabs Speech** - Advanced TTS with v3 model, 50+ audio tags, 74 languages ([Documentation](tools/mcp/mcp_elevenlabs_speech/docs/README.md))
11. **Video Editor** - AI-powered video editing with transcription and scene detection ([Documentation](tools/mcp/mcp_video_editor/docs/README.md))
12. **Virtual Character** - AI agent embodiment in virtual worlds (VRChat, Blender, Unity) ([Documentation](tools/mcp/mcp_virtual_character/README.md))
13. **GitHub Board** - GitHub Projects v2 board management, work claiming, agent coordination ([Documentation](tools/mcp/mcp_github_board/docs/README.md))
14. **AI Toolkit** - LoRA training interface (remote: 192.168.0.152:8012)
15. **ComfyUI** - Image generation interface (remote: 192.168.0.152:8013)
16. **AgentCore Memory** - Multi-provider AI memory (AWS AgentCore or ChromaDB) ([Documentation](tools/mcp/mcp_agentcore_memory/docs/README.md))
17. **Reaction Search** - Semantic search for anime reaction images ([Documentation](tools/mcp/mcp_reaction_search/README.md))
18. **Desktop Control** - Cross-platform desktop automation for Linux and Windows ([Documentation](tools/mcp/mcp_desktop_control/docs/README.md))

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
- `AGENTS.md` - Universal AI agent configuration and guidelines (root directory)
- `docs/agents/project-context.md` - Context for AI reviewers

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
- [MCP Architecture](docs/mcp/README.md) - Modular server design
- [AI Agents Documentation](docs/agents/README.md) - AI agents overview

### Quick References
- [Codex Setup Guide](docs/agents/codex-setup.md)
- [AI Code Agents Quick Reference](docs/integrations/ai-services/ai-code-agents-ref.md)
- [MCP Tools Reference](docs/mcp/tools.md)
- [Gaea2 Quick Reference](tools/mcp/mcp_gaea2/docs/GAEA2_QUICK_REFERENCE.md)

### Integration Guides
- [Codex Integration](docs/agents/codex-setup.md)
- [AI Code Agents Integration](docs/integrations/ai-services/ai-code-agents.md)
- [AI Toolkit & ComfyUI Integration](docs/integrations/creative-tools/ai-toolkit-comfyui.md)
- [Gaea2 Documentation](tools/mcp/mcp_gaea2/docs/README.md)

### Setup & Configuration
- **[Template Quickstart Guide](docs/QUICKSTART.md)** - Customize the template for your needs
- [Self-Hosted Runner Setup](docs/infrastructure/self-hosted-runner.md)
- [GitHub Environments Setup](docs/infrastructure/github-environments.md)
- [Containerized CI](docs/infrastructure/containerization.md)

## License

This project is released under the [Unlicense](LICENSE) (public domain dedication).

**For jurisdictions that do not recognize public domain:** As a fallback, this project is also available under the [MIT License](LICENSE-MIT).
