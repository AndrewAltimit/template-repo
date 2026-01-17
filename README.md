# Agent Orchestration & Security Template

An AI safety engineering portfolio combining production tooling, detection research, and risk analysis—structured as a reusable template.

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

## Quick Start

> **New to the template?** Check out our **[Template Quickstart Guide](docs/QUICKSTART.md)** for step-by-step customization instructions!

1. **Prerequisites**: Linux system with Docker (v20.10+) and Docker Compose (v2.0+)

2. **Clone and setup**
   ```bash
   git clone https://github.com/AndrewAltimit/template-repo
   cd template-repo
   pip3 install -e ./packages/github_agents
   ```

3. **Set API keys** (if using AI features)
   ```bash
   export OPENROUTER_API_KEY="your-key-here"  # For OpenCode/Crush
   export GEMINI_API_KEY="your-key-here"      # For Gemini
   ```

4. **Use with Claude Code**: MCP servers are configured in `.mcp.json` and auto-started by Claude. See [MCP Configuration](docs/mcp/README.md#configuration-strategy) for essential vs full setups.

5. **Run CI/CD operations**
   ```bash
   ./automation/ci-cd/run-ci.sh full  # Full pipeline
   ```

For detailed setup, see [CLAUDE.md](CLAUDE.md) and [Template Quickstart Guide](docs/QUICKSTART.md).

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

### Agentic Git Workflow

AI agents autonomously manage the development lifecycle from issue creation through PR merge:

```
Issue Created → Admin Approval → Agent Claims → PR Created → AI Review → Human Merge
```

**The Flow:**

1. **Issue Creation** - Issues are created manually or by agents via `backlog-refinement.yml`, automatically added to the GitHub Projects board
2. **Admin Approval** - An authorized user comments `[Approved][Claude]` (or another agent name) to authorize work
3. **Agent Claims** - `board-agent-worker.yml` finds approved issues, the agent claims the issue and creates a working branch
4. **Implementation** - The agent implements the fix/feature and opens a PR
5. **AI Review** - `pr-validation.yml` triggers Gemini code review; `pr-review-monitor.yml` lets agents iterate on feedback
6. **Human Merge** - Admin reviews and merges the PR

**Security Model:**

- **Approval Required** - Agents cannot work on issues without explicit `[Approved][Agent]` comment
- **Authorized Users Only** - Only users listed in `.agents.yaml` → `security.agent_admins` can approve
- **Pattern Validation** - Must use `[Action][Agent]` format (e.g., `[Approved][Claude]`) to prevent false positives
- **Claim Tracking** - Agents post claim comments with timestamps to prevent conflicts

See [Security Documentation](packages/github_agents/docs/security.md) for the complete security model.

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
| **Agentic Workflow Handout** | AI agent pipeline architecture and workflows | [Download](https://github.com/AndrewAltimit/template-repo/releases/latest) | [LaTeX](docs/agents/Agentic_Workflow_Handout.tex) |
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

Four standalone packages addressing different aspects of AI agent development and safety:

| Package | Purpose | Documentation |
|---------|---------|---------------|
| **[GitHub Agents](packages/github_agents/)** | Multi-agent orchestration for autonomous GitHub workflows - issue monitoring, PR review processing, and board coordination with Claude, Codex, OpenCode, Gemini, and Crush | [README](packages/github_agents/README.md) \| [Security](packages/github_agents/docs/security.md) |
| **[Sleeper Agents](packages/sleeper_agents/)** | Production-validated detection framework for hidden backdoors in LLMs, based on Anthropic's research on deceptive AI that persists through safety training | [README](packages/sleeper_agents/README.md) \| [PDF Guide](https://github.com/AndrewAltimit/template-repo/releases/latest) |
| **[Economic Agents](packages/economic_agents/)** | Simulation framework demonstrating autonomous AI economic capability - agents that earn money, form companies, hire sub-agents, and seek investment. For governance research and policy development | [README](packages/economic_agents/README.md) |
| **[Injection Toolkit](packages/injection_toolkit/)** | Cross-platform Rust framework for runtime integration - DLL injection (Windows), LD_PRELOAD (Linux), shared memory IPC, and overlay rendering. For game modding, debugging tools, and AI agent embodiment | [README](packages/injection_toolkit/README.md) \| [Architecture](packages/injection_toolkit/docs/ARCHITECTURE.md) |

```bash
# Install Python packages
pip install -e ./packages/github_agents
pip install -e ./packages/sleeper_agents
pip install -e ./packages/economic_agents

# Build Rust package (requires Rust toolchain)
cd packages/injection_toolkit && cargo build --release
```

## Features

- **[18 MCP Servers](#mcp-servers)** - Code quality, content creation, AI assistance, 3D graphics, video editing, speech synthesis, and more
- **[6 AI Agents](#ai-agents)** - Autonomous development workflow from issue to merge
- **[4 Packages](#packages)** - GitHub automation, sleeper agent detection, economic agent simulation, runtime injection toolkit
- **Container-First Architecture** - Maximum portability and consistency
- **Self-Hosted CI/CD** - Zero-cost GitHub Actions infrastructure
- **Company Integration** - Corporate proxy builds for enterprise AI APIs ([Docs](automation/corporate-proxy/shared/docs/ARCHITECTURE.md))

## Enterprise & Corporate Setup

For enterprise environments requiring custom certificates, customize [`automation/corporate-proxy/shared/scripts/install-corporate-certs.sh`](automation/corporate-proxy/shared/scripts/install-corporate-certs.sh). This script runs during Docker builds for all containers. See the [customization guide](automation/corporate-proxy/shared/scripts/README.md) for details.

## Project Structure

```
.
├── .github/workflows/        # GitHub Actions workflows
├── docker/                   # Docker configurations
├── packages/                 # Installable packages
│   ├── github_agents/        # Multi-agent GitHub automation
│   ├── sleeper_agents/       # AI backdoor detection framework
│   ├── economic_agents/      # Autonomous economic agents
│   └── injection_toolkit/    # Rust runtime injection framework
├── tools/
│   ├── mcp/                  # 18 MCP servers (see MCP Servers section)
│   └── cli/                  # Agent runners and utilities
├── automation/               # CI/CD and automation scripts
├── tests/                    # Test files
├── docs/                     # Documentation
└── config/                   # Configuration files
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
14. **AI Toolkit** - LoRA training interface (remote: 192.168.0.222:8012)
15. **ComfyUI** - Image generation interface (remote: 192.168.0.222:8013)
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
