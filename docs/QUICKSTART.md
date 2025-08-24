# Template Quickstart Guide

**🚀 Transform this template into your perfect development environment in 15 minutes**

This guide helps you customize the MCP-Enabled Project Template for your specific needs. Whether you're building a solo project, team application, or just want specific tools, this guide shows you exactly what to enable, disable, and configure.

## Table of Contents

1. [Understanding the Template](#understanding-the-template)
2. [Choose Your Setup Path](#choose-your-setup-path)
3. [Step-by-Step Customization](#step-by-step-customization)
4. [Common Configurations](#common-configurations)
5. [Testing Your Setup](#testing-your-setup)
6. [Troubleshooting](#troubleshooting)

## Understanding the Template

This template includes:
- **13 MCP Servers** - Modular tools (enable only what you need)
- **7 AI Agents** - Development automation (all optional)
- **Container-First Architecture** - Everything runs in Docker
- **Self-Hosted CI/CD** - GitHub Actions automation
- **Zero External Dependencies** - Just Docker required

### What Can Be Customized?

✅ **Enable/Disable Any Component:**
- MCP servers (code quality, content creation, etc.)
- AI agents (Claude, Gemini, OpenCode, etc.)
- CI/CD workflows
- Remote services (Gaea2, ComfyUI, AI Toolkit)

✅ **Replace With Your Own:**
- API keys and authentication
- Remote server addresses
- Docker configurations
- GitHub workflows

## Choose Your Setup Path

### 🎯 Path A: Minimal Setup (Just the Essentials)
**Perfect for:** Small projects, learning MCP, quick prototypes

**What you get:**
- Code quality tools (formatting, linting)
- Basic CI/CD
- No AI agents or complex servers

[Jump to Minimal Setup](#minimal-setup)

### 🎯 Path B: AI-Powered Development
**Perfect for:** Solo developers, AI-assisted coding

**What you get:**
- Code quality + AI code generation
- OpenCode/Crush for code assistance
- Optional Gemini for reviews

[Jump to AI-Powered Setup](#ai-powered-setup)

### 🎯 Path C: Content Creation Suite
**Perfect for:** Technical content, documentation, visualizations

**What you get:**
- Manim animations, LaTeX documents
- Video editing, speech synthesis
- Meme generation for documentation

[Jump to Content Creation Setup](#content-creation-setup)

### 🎯 Path D: Full Stack Everything
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
   # ⚠️ CAUTION: This command deletes the existing Git history.
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

**Time Required:** 5 minutes

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
   # No need to install github_ai_agents package
   # Skip API key setup
   ```

4. **Test your minimal setup:**
   ```bash
   # Start only essential services
   docker-compose up -d python-ci mcp-code-quality

   # Run code quality checks
   ./automation/ci-cd/run-ci.sh format
   ./automation/ci-cd/run-ci.sh lint-basic
   ```

### AI-Powered Setup

**Time Required:** 10 minutes

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
         "command": "python",
         "args": ["-m", "tools.mcp.opencode.server"],
         "env": {
           "OPENROUTER_API_KEY": "{OPENROUTER_API_KEY}"
         }
       },
       "crush": {
         "command": "python",
         "args": ["-m", "tools.mcp.crush.server"],
         "env": {
           "OPENROUTER_API_KEY": "{OPENROUTER_API_KEY}"
         }
       },
       "gemini": {
         "command": "python",
         "args": ["-m", "tools.mcp.gemini.server"],
         "env": {
           "GEMINI_API_KEY": "{GEMINI_API_KEY}"
         }
       }
     }
   }
   ```

3. **Install AI agents (optional):**
   ```bash
   # For CLI access to agents
   pip3 install -e ./packages/github_ai_agents
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

### Content Creation Setup

**Time Required:** 10 minutes

1. **Enable content MCP servers in `.mcp.json`:**
   ```json
   {
     "mcpServers": {
       "content-creation": {
         "command": "python",
         "args": ["-m", "tools.mcp.content_creation.server"]
       },
       "meme-generator": {
         "command": "python",
         "args": ["-m", "tools.mcp.meme_generator.server"]
       },
       "elevenlabs-speech": {
         "command": "python",
         "args": ["-m", "tools.mcp.elevenlabs_speech.server"],
         "env": {
           "ELEVENLABS_API_KEY": "{ELEVENLABS_API_KEY}"
         }
       },
       "video-editor": {
         "command": "python",
         "args": ["-m", "tools.mcp.video_editor.server"]
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
   docker-compose up -d mcp-content-creation mcp-video-editor
   ```

4. **Test content creation:**
   ```bash
   # Test server health
   python automation/testing/test_all_servers.py --quick
   ```

### Full Stack Setup

**Time Required:** 15 minutes

1. **Enable all MCP servers** (keep default `.mcp.json`)

2. **Configure all API keys in `.env`:**
   ```bash
   OPENROUTER_API_KEY="your-key"
   GEMINI_API_KEY="your-key"
   ELEVENLABS_API_KEY="your-key"
   GITHUB_TOKEN="your-token"
   ```

3. **Set up remote services (optional):**
   ```bash
   # For Gaea2 (terrain generation)
   GAEA2_REMOTE_HOST="192.168.0.152"  # Or your Windows machine IP
   GAEA2_REMOTE_PORT="8007"

   # For AI Toolkit & ComfyUI
   AI_TOOLKIT_URL="http://192.168.0.152:8012"
   COMFYUI_URL="http://192.168.0.152:8013"
   ```

4. **Install all components:**
   ```bash
   # Install AI agents
   pip3 install -e ./packages/github_ai_agents

   # Start all services
   docker-compose up -d

   # Verify everything is running
   docker-compose ps
   python automation/testing/test_all_servers.py
   ```

## Common Configurations

### Disabling Specific Features

#### Disable All AI Agents
```bash
# Remove from .mcp.json
# Don't install github_ai_agents package
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
docker-compose up -d
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
# Run full CI to verify setup
./automation/ci-cd/run-ci.sh full

# Or test individually
./automation/ci-cd/run-ci.sh format
./automation/ci-cd/run-ci.sh test
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
docker-compose ps

# Check logs
docker-compose logs mcp-code-quality

# Restart service
docker-compose restart mcp-code-quality
```

#### "API key not working"
```bash
# Verify .env file
cat .env | grep API_KEY

# Restart services after changing .env
docker-compose down
docker-compose up -d
```

#### "Permission denied errors"
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
# Log out and back in

# Fix file permissions
sudo chown -R $USER:$USER .
```

### Getting Help

1. **Check existing documentation:**
   - [MCP Architecture](./mcp/README.md)
   - [AI Agents Overview](./ai-agents/README.md)
   - [Infrastructure Setup](./infrastructure/README.md)

2. **Review example configurations:**
   - `.env.example` - All available environment variables
   - `.mcp.json` - Full MCP server configuration
   - `docker-compose.yml` - All service definitions

3. **Debug commands:**
   ```bash
   # Check Docker status
   docker-compose ps
   docker-compose logs [service-name]

   # Test individual servers
   python tools/mcp/code_quality/scripts/test_server.py
   python tools/mcp/gemini/scripts/test_server.py

   # Validate configuration
   python automation/testing/validate_config.py
   ```

## Next Steps

After customizing your template:

1. **Remove unused code:**
   ```bash
   # Remove MCP servers you're not using
   rm -rf tools/mcp/[unused-server]/

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

**🎉 Congratulations!** You've successfully customized the template for your needs. The modular architecture means you can always add or remove components later as your project evolves.

**Remember:** Start simple and add complexity only when needed. You can always enable more features later!
