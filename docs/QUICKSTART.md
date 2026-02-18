# Template Quickstart Guide

This guide helps you fork and adapt this template for your own projects. The components are modular -- you are expected to pick and choose what you need, not use everything.

**What to expect:** The MCP servers, packages, and CI/CD tools are designed to work independently. You can enable a single MCP server (e.g., code-quality) without touching the rest. However, the agent orchestration system (board-driven workflows, PR review pipelines, security wrappers) is tightly integrated and requires more effort to adapt.

## Table of Contents

1. [Before You Start: What You Need to Change](#before-you-start-what-you-need-to-change)
2. [Understanding the Template](#understanding-the-template)
3. [Choose Your Setup Path](#choose-your-setup-path)
4. [Step-by-Step Customization](#step-by-step-customization)
5. [Common Configurations](#common-configurations)
6. [Testing Your Setup](#testing-your-setup)
7. [Troubleshooting](#troubleshooting)

## Before You Start: What You Need to Change

This template was built for a specific infrastructure. When forking, you will need to update the following to match your own environment:

### Required Changes

| What | Where | Why |
|------|-------|-----|
| **GitHub repository references** | `.agents.yaml`, workflow files, README.md | Repo URLs point to `AndrewAltimit/template-repo` |
| **`agent_admins` list** | `.agents.yaml` | Controls who can approve agent work -- must be your GitHub username |
| **GitHub Projects board ID** | `ai-agents-board.yml` | The board ID is specific to the original repo's GitHub Projects v2 board |

### API Keys (per feature)

| Key | Required For | How to Get |
|-----|-------------|------------|
| `OPENROUTER_API_KEY` | OpenCode, Crush MCP servers | [openrouter.ai](https://openrouter.ai/) |
| `GOOGLE_API_KEY` | Gemini MCP server | [Google AI Studio](https://aistudio.google.com/) |
| `ELEVENLABS_API_KEY` | ElevenLabs Speech MCP server | [elevenlabs.io](https://elevenlabs.io/) |
| `GITHUB_TOKEN` | Agent workflows, board-manager, gh-validator | GitHub Settings > Developer Settings > Fine-grained tokens |
| `CODEX_API_KEY` | Codex MCP server | [OpenAI](https://platform.openai.com/) |

You only need keys for the features you enable. The Minimal setup path requires no API keys at all.

### Remote Server Addresses

The template references machines on the maintainer's LAN. These will not work for you and should be removed or replaced:

| Address | Service | What to Do |
|---------|---------|------------|
| `192.168.0.152:8007` | Gaea2 terrain generation | Remove from `.mcp.json`, or replace with your own Windows machine running Gaea2 |
| `192.168.0.222:8012` | AI Toolkit (LoRA training) | Remove, or replace with your own GPU machine |
| `192.168.0.222:8013` | ComfyUI (image generation) | Remove, or replace with your own GPU machine |

These addresses appear in `.mcp.json.full`, `docker-compose.yml`, and some documentation files. If you don't have dedicated GPU hardware for these services, simply delete them from your configuration.

### Self-Hosted Runner

The CI/CD workflows are configured for a self-hosted GitHub Actions runner. If you use GitHub-hosted runners instead, you will need to change `runs-on: self-hosted` to `runs-on: ubuntu-latest` (or similar) in the workflow YAML files. Some features (Docker builds, GPU evaluation) require self-hosted runners.

## Understanding the Template

This template includes:
- **19 MCP Servers** - Modular tools (enable only what you need)
- **6 AI Agents** - Development automation (all optional)
- **Container-First Architecture** - Everything runs in Docker
- **Self-Hosted CI/CD** - GitHub Actions automation
- **Zero External Dependencies** - Just Docker required

### MCP Configuration Files

The template provides two MCP configuration files to optimize performance:

**`.mcp.json` (Default - Essential Services):**
- Contains only essential services to prevent context window overload
- Includes: code-quality, AI agents (Gemini, OpenCode, Crush, Codex)
- Best for day-to-day development and code review
- **Recommended for most users**

**`.mcp.json.full` (Complete - All Services):**
- Contains all 19 MCP servers including specialized tools
- Includes: content creation, 3D graphics, media tools, remote services
- Use when you need specialized content creation or media processing
- Switch to this configuration only when needed to avoid overloading Claude's context window

**Why two configs?** Claude Code loads all MCP tool definitions into its context window. Having too many tools can reduce performance and response quality. By default, use `.mcp.json` with essential services, and only switch to `.mcp.json.full` when you need specialized tools.

### What Can Be Customized?

**Enable/Disable Any Component:**
- MCP servers (code quality, content creation, etc.)
- AI agents (Claude, Gemini, OpenCode, etc.)
- CI/CD workflows
- Remote services (Gaea2, ComfyUI, AI Toolkit)

**Replace With Your Own:**
- API keys and authentication
- Remote server addresses
- Docker configurations
- GitHub workflows

## Choose Your Setup Path

### Path A: Minimal Setup (Just the Essentials)
**Perfect for:** Small projects, learning MCP, quick prototypes

**What you get:**
- Code quality tools (formatting, linting)
- Basic CI/CD
- No AI agents or complex servers

[Jump to Minimal Setup](#minimal-setup)

### Path B: AI-Powered Development
**Perfect for:** Solo developers, AI-assisted coding

**What you get:**
- Code quality + AI code generation
- OpenCode/Crush for code assistance
- Optional Gemini for reviews

[Jump to AI-Powered Setup](#ai-powered-setup)

### Path C: Content Creation Suite
**Perfect for:** Technical content, documentation, visualizations

**What you get:**
- Manim animations, LaTeX documents
- Video editing, speech synthesis
- Meme generation for documentation

[Jump to Content Creation Setup](#content-creation-setup)

### Path D: Full Stack Everything
**Perfect for:** Complex projects, teams, maximum automation

**What you get:**
- All MCP servers and AI agents
- Complete CI/CD automation
- Remote GPU services

[Jump to Full Stack Setup](#full-stack-setup)

## Step-by-Step Customization

### Initial Setup (Required for All Paths)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AndrewAltimit/template-repo your-project-name
   cd your-project-name
   # CAUTION: This command deletes the existing Git history.
   rm -rf .git  # Detach from the template's history to start your own project
   git init     # Start fresh with your own Git history
   ```

2. **Install Docker (if not already installed):**
   ```bash
   # Ubuntu/Debian
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   # Log out and back in for group changes to take effect
   ```

3. **Create your environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

### Minimal Setup

**Requires:** Docker only (no API keys)

1. **Disable unnecessary MCP servers in `.mcp.json`:**
   ```json
   {
     "mcpServers": {
       "code-quality": { /* Keep this */ },
       // Comment out or remove other servers
     }
   }
   ```

2. **Simplify docker-compose.yml:**
   ```yaml
   version: '3.8'
   services:
     python-ci:
       # Keep this for testing
     mcp-code-quality:
       # Keep this for code quality
     # Remove or comment out other services
   ```

3. **Remove AI agent dependencies:**
   ```bash
   # No need to install github_agents package
   # Skip API key setup
   ```

4. **Test your minimal setup:**
   ```bash
   # Start only essential services
   docker compose up -d python-ci mcp-code-quality

   # Run code quality checks
   automation-cli ci run format
   automation-cli ci run lint-basic
   ```

### AI-Powered Setup

**Requires:** Docker + at least one API key (OpenRouter, Gemini, or OpenAI)

1. **Configure AI services in `.env`:**
   ```bash
   # For OpenCode/Crush
   OPENROUTER_API_KEY="your-openrouter-key"

   # For Gemini (optional)
   GEMINI_API_KEY="your-gemini-key"  # Or use web auth for free tier
   ```

2. **Enable AI MCP servers in `.mcp.json`:**
   ```json
   {
     "mcpServers": {
       "code-quality": { /* ... */ },
       "opencode": {
         "command": "mcp-opencode",
         "args": ["--mode", "stdio"],
         "env": {
           "OPENROUTER_API_KEY": "{OPENROUTER_API_KEY}"
         }
       },
       "crush": {
         "command": "mcp-crush",
         "args": ["--mode", "stdio"],
         "env": {
           "OPENROUTER_API_KEY": "{OPENROUTER_API_KEY}"
         }
       },
       "gemini": {
         "command": "mcp-gemini",
         "args": ["--mode", "stdio"],
         "env": {
           "GOOGLE_API_KEY": "{GOOGLE_API_KEY}"
         }
       }
     }
   }
   ```

3. **Build GitHub Agents CLI (optional):**
   ```bash
   # Build the Rust CLI for issue/PR monitoring
   cd tools/rust/github-agents-cli && cargo build --release
   ```

4. **Test AI features:**
   ```bash
   # Test OpenCode
   ./tools/cli/agents/run_opencode.sh -q "Write a Python fibonacci function"

   # Test Crush
   ./tools/cli/agents/run_crush.sh -q "Convert this to TypeScript: def add(a, b): return a + b"

   # Test Gemini (if configured)
   ./tools/cli/agents/run_gemini.sh
   ```

**Safety Training**: Before deploying AI agents in production, review the [AI Safety Training Guide](agents/human-training.md) to understand potential risks, deceptive behaviors, and safety protocols for human-AI collaboration.

### Content Creation Setup

**Requires:** Docker + optional ElevenLabs API key for speech

1. **Enable content MCP servers in `.mcp.json`:**
   ```json
   {
     "mcpServers": {
       "content-creation": {
         "command": "python",
         "args": ["-m", "mcp_content_creation.server"]
       },
       "meme-generator": {
         "command": "python",
         "args": ["-m", "mcp_meme_generator.server"]
       },
       "elevenlabs-speech": {
         "command": "python",
         "args": ["-m", "mcp_elevenlabs_speech.server"],
         "env": {
           "ELEVENLABS_API_KEY": "{ELEVENLABS_API_KEY}"
         }
       },
       "video-editor": {
         "command": "python",
         "args": ["-m", "mcp_video_editor.server"]
       }
     }
   }
   ```

2. **Configure API keys (if using speech):**
   ```bash
   # In .env
   ELEVENLABS_API_KEY="your-elevenlabs-key"
   ```

3. **Start content services:**
   ```bash
   docker compose up -d mcp-content-creation mcp-video-editor
   ```

4. **Test content creation:**
   ```bash
   # Test server health
   python automation/testing/test_all_servers.py --quick
   ```

### Full Stack Setup

**Requires:** Docker, Rust toolchain, all API keys, self-hosted GitHub Actions runner. Remote GPU services (Gaea2, AI Toolkit, ComfyUI) require dedicated hardware on your network.

> **Note:** This path requires the most adaptation. You will need to update remote server addresses, GitHub Projects board IDs, the `agent_admins` list, and workflow runner labels. See [Before You Start](#before-you-start-what-you-need-to-change) for the full list.

1. **Enable all MCP servers** (use `.mcp.json.full` as your starting point)

2. **Configure all API keys in `.env`:**
   ```bash
   OPENROUTER_API_KEY="your-key"
   GEMINI_API_KEY="your-key"
   ELEVENLABS_API_KEY="your-key"
   GITHUB_TOKEN="your-token"
   ```

3. **Set up remote services (if you have the hardware):**
   ```bash
   # For Gaea2 (requires a Windows machine running Gaea2)
   GAEA2_REMOTE_HOST="your-windows-machine-ip"
   GAEA2_REMOTE_PORT="8007"

   # For AI Toolkit & ComfyUI (requires a machine with an NVIDIA GPU)
   AI_TOOLKIT_URL="http://your-gpu-machine-ip:8012"
   COMFYUI_URL="http://your-gpu-machine-ip:8013"
   ```
   If you don't have dedicated hardware for these, remove the `gaea2`, `ai-toolkit`, and `comfyui` entries from `.mcp.json` and their services from `docker-compose.yml`.

4. **Install all components:**
   ```bash
   # Build GitHub Agents CLI (Rust)
   cd tools/rust/github-agents-cli && cargo build --release
   cd ../../..  # Return to project root

   # Start all services
   docker compose up -d

   # Verify everything is running
   docker compose ps
   python automation/testing/test_all_servers.py
   ```

## Common Configurations

### Disabling Specific Features

#### Disable All AI Agents
```bash
# Remove from .mcp.json
# Skip building GitHub Agents CLI
# Remove AI-related GitHub workflows
rm -f .github/workflows/pr-validation.yml
rm -f .github/workflows/issue-monitor.yml
```

#### Disable Remote Services
```json
// In .mcp.json, remove:
"gaea2": { /* ... */ },
"ai-toolkit": { /* ... */ },
"comfyui": { /* ... */ }
```

#### Disable GitHub Actions
```bash
# Remove workflows you don't need
rm -rf .github/workflows/
# Or selectively keep what you want
```

### Configuring for Your Infrastructure

#### Using Different Ports
```yaml
# In docker-compose.yml
services:
  mcp-code-quality:
    ports:
      - "9010:8010"  # Change host port
```

#### Using Different Remote Servers
```bash
# In .env
GAEA2_REMOTE_HOST="your-server.com"
AI_TOOLKIT_URL="http://your-gpu-server:8012"
```

#### Running Everything Locally
```bash
# Remove remote server configurations
# Run all MCP servers in HTTP mode locally
docker compose up -d
```

### Project-Specific Customization

#### For Python Projects
```json
// Keep these MCP servers:
"code-quality": { /* ... */ },  // Formatting & linting
"gemini": { /* ... */ }         // Code review
```

#### For Web Development
```json
// Add these:
"code-quality": { /* ... */ },  // ESLint, Prettier support
"opencode": { /* ... */ },       // AI code generation
"crush": { /* ... */ }           // Quick conversions
```

#### For Documentation Projects
```json
// Focus on:
"content-creation": { /* ... */ },  // LaTeX, diagrams
"meme-generator": { /* ... */ },    // Visual elements
"elevenlabs-speech": { /* ... */ }  // Audio documentation
```

#### For ML/AI Projects
```json
// Include:
"ai-toolkit": { /* ... */ },     // LoRA training
"comfyui": { /* ... */ },        // Image generation
"blender": { /* ... */ }         // 3D visualization
```

## Testing Your Setup

### Quick Health Check
```bash
# Test all enabled servers
python automation/testing/test_all_servers.py --quick

# Test specific server
curl http://localhost:8010/health  # Code quality
curl http://localhost:8011/health  # Content creation
```

### Verify MCP Tools in Claude Code
1. Open Claude Code (claude.ai/code)
2. Check that your MCP tools appear in the tools list
3. Test a simple command for each server

### Run CI Pipeline
```bash
# Build the automation CLI (one-time)
cargo build --release -p automation-cli

# Run full CI to verify setup
automation-cli ci run full

# Or test individually
automation-cli ci run format
automation-cli ci run test
```

## Troubleshooting

### Common Issues and Solutions

#### "Port already in use"
```bash
# Check what's using the port
sudo lsof -i :8010

# Change port in docker-compose.yml
# Or stop conflicting service
```

#### "MCP server not responding"
```bash
# Check if container is running
docker compose ps

# Check logs
docker compose logs mcp-code-quality

# Restart service
docker compose restart mcp-code-quality
```

#### "API key not working"
```bash
# Verify .env file
cat .env | grep API_KEY

# Restart services after changing .env
docker compose down
docker compose up -d
```

#### "Permission denied errors"
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
# Log out and back in

# Fix file permissions
sudo chown -R $USER:$USER .
```

### Troubleshooting Resources

> **Note:** The maintainer does not provide support, guidance, or consulting for users of this template. You are on your own. See [CONTRIBUTING.md](../CONTRIBUTING.md).

1. **Check existing documentation:**
   - [MCP Architecture](./mcp/README.md)
   - [AI Agents Overview](./agents/README.md)
   - [Infrastructure Setup](./infrastructure/README.md)

2. **Review example configurations:**
   - `.env.example` - All available environment variables
   - `.mcp.json` - Full MCP server configuration
   - `docker-compose.yml` - All service definitions

3. **Debug commands:**
   ```bash
   # Check Docker status
   docker compose ps
   docker compose logs [service-name]

   # Test Python MCP servers
   python tools/mcp/mcp_code_quality/scripts/test_server.py

   # Test Rust MCP servers (health endpoint)
   curl http://localhost:8006/health  # mcp-gemini
   curl http://localhost:8014/health  # mcp-opencode
   curl http://localhost:8015/health  # mcp-crush
   curl http://localhost:8021/health  # mcp-codex

   # Validate configuration
   python automation/testing/validate_config.py
   ```

## Next Steps

After customizing your template:

1. **Remove unused code:**
   ```bash
   # Remove MCP servers you're not using
   rm -rf tools/mcp/mcp_[unused-server]/

   # Remove unused documentation
   rm -rf docs/integrations/[unused-integration]/
   ```

2. **Update documentation:**
   - Edit `README.md` to reflect your configuration
   - Update `CLAUDE.md` with your project-specific instructions
   - Remove references to disabled features

3. **Commit your customized template:**
   ```bash
   git add .
   git commit -m "Customize template for [your project type]"
   git remote add origin [your-repo-url]
   git push -u origin main
   ```

4. **Set up CI/CD (optional):**
   - Configure GitHub secrets for your API keys
   - Set up self-hosted runner (see [guide](./infrastructure/self-hosted-runner.md))
   - Enable only workflows you need

---

The modular architecture means you can always add or remove components later as your project evolves. Start simple and add complexity only when needed.
