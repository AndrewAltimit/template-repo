# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**For Claude's expression philosophy and communication style, see** `docs/agents/claude-expression.md`

## Project Context

This is a **single-maintainer project** by @AndrewAltimit with a **container-first philosophy**:

- All Python and Rust operations run in Docker containers
- Self-hosted infrastructure for zero-cost operation
- Designed for maximum portability - works on any Linux system with Docker
- No contributors model - optimized for individual developer efficiency

## AI Agent Collaboration

You are working alongside five other AI agents:

1. **Codex** - AI-powered code generation (OpenAI)
2. **OpenCode** - Code generation via OpenRouter
3. **Crush** - Code generation via OpenRouter
4. **Gemini CLI** - Automated PR code reviews
5. **GitHub Copilot** - Code review suggestions in PRs

Your role as Claude Code is the primary development assistant.

**For complete agent documentation, see** `docs/agents/README.md`
**For security model, see** `docs/agents/security.md`

### Remote Infrastructure

**IMPORTANT**: Some MCP servers run on dedicated remote machines:
- Gaea2 MCP: `192.168.0.152:8007` (requires Windows with Gaea2)
- AI Toolkit/ComfyUI: `192.168.0.222` (requires GPU)
- Do NOT change remote addresses to localhost in PR reviews

## Essential Commands

### CI/CD (Most Used)

```bash
# Python
./automation/ci-cd/run-ci.sh full        # All Python checks
./automation/ci-cd/run-ci.sh format      # Check formatting
./automation/ci-cd/run-ci.sh lint-full   # Full linting

# Rust
./automation/ci-cd/run-ci.sh rust-full   # All Rust checks
./automation/ci-cd/run-ci.sh econ-full   # Economic agents (fmt + clippy + test)

# Context protection - ALWAYS use for verbose output
./automation/ci-cd/run-ci.sh full > /tmp/ci-output.log 2>&1 && echo "CI passed" || (echo "CI failed - check /tmp/ci-output.log"; exit 1)
```

### PR Monitoring

```bash
./tools/rust/pr-monitor/target/release/pr-monitor 48
./tools/rust/pr-monitor/target/release/pr-monitor 48 --since-commit abc1234
```

**For complete command reference, see** `docs/agents/README.md#running-agents-locally`

### Docker Operations

```bash
docker-compose up -d                     # Start all services
docker-compose logs -f <service>         # View logs
docker-compose down                      # Stop services
```

## Architecture

### MCP Servers

18 modular MCP servers providing specialized functionality:

| Category | Servers | Transport |
|----------|---------|-----------|
| Code Quality | code-quality, gemini, opencode, crush, codex | STDIO (local) |
| Content | content-creation, meme-generator, elevenlabs-speech, video-editor, blender | STDIO |
| Integration | virtual-character, github-board, agentcore-memory, reaction-search, desktop-control | STDIO |
| Remote | gaea2, ai-toolkit, comfyui | HTTP (remote machines) |

**For complete MCP documentation, see** `docs/mcp/README.md`

### Container Architecture

1. **Everything Containerized** (with documented exceptions)
2. **Zero Local Dependencies** - All via Docker Compose
3. **Self-Hosted Infrastructure** - No cloud costs

**For details, see** `docs/infrastructure/containerization.md`

### Research Packages

| Package | Language | Purpose |
|---------|----------|---------|
| `packages/sleeper_agents/` | Python | Sleeper agent detection framework |
| `packages/economic_agents/` | Rust | Autonomous AI economic simulation |
| `packages/injection_toolkit/` | Rust | Cross-platform screen capture/injection |

## Development Reminders

- **ALWAYS run CI checks** after completing work (see commands above)
- **NEVER commit** unless the user explicitly asks
- **Follow container-first philosophy** - use Docker for all operations
- **NEVER use Unicode emoji** in code, commits, or comments
- Use reaction images for GitHub interactions instead

## GitHub Etiquette

- **NEVER use @ mentions** except for @AndrewAltimit
- Refer to AI agents without @: "Gemini", "Claude", "OpenAI"
- Use reaction-search MCP server for PR comment reactions
- **Use `gh api` instead of `gh pr edit`** for PR updates

### Reaction Images

Use the `reaction-search` MCP server for contextually appropriate reactions:

```python
search_reactions(query="celebrating after fixing a bug", limit=3)
get_reaction(reaction_id="miku_typing")
```

**Example PR comment with reaction:**

```markdown
Fixed the race condition in the worker pool. The issue was a missing lock
on the shared counter - now using AtomicUsize instead.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_typing.webp)
```

This renders as:

> Fixed the race condition in the worker pool. The issue was a missing lock
> on the shared counter - now using AtomicUsize instead.
>
> ![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_typing.webp)

**CRITICAL**: Use Write tool + `--body-file` pattern for PR comments (shell escaping breaks `![]`).

**For complete GitHub etiquette, see** `docs/agents/github-etiquette.md`

## Documentation Index

### Core
- `docs/README.md` - Documentation overview
- `docs/QUICKSTART.md` - Template quickstart guide

### AI Agents
- `docs/agents/README.md` - Agent system overview
- `docs/agents/security.md` - Security documentation
- `docs/agents/board-workflow.md` - Board-centric workflow guide
- `docs/agents/pr-monitoring.md` - PR monitoring documentation
- `docs/agents/human-training.md` - AI safety training guide

### MCP
- `docs/mcp/README.md` - MCP architecture
- `docs/mcp/servers.md` - Server reference
- `docs/mcp/tools.md` - Tools reference

### Infrastructure
- `docs/infrastructure/containerization.md` - Container philosophy
- `docs/infrastructure/self-hosted-runner.md` - Runner setup
- `docs/developer/claude-code-hooks.md` - Hook system

### Integrations
- `docs/integrations/ai-services/ai-code-agents.md` - AI code agents
- `docs/integrations/creative-tools/ai-toolkit-comfyui.md` - LoRA training
- `docs/integrations/creative-tools/virtual-character-elevenlabs.md` - Virtual character system

### Research Packages
- `packages/sleeper_agents/README.md` - Sleeper agent detection
- `packages/economic_agents/README.md` - Economic agents simulation (Rust)
- `packages/economic_agents/docs/economic-implications.md` - **AI governance policy analysis**
- `packages/injection_toolkit/README.md` - Injection toolkit
