# Installation Guide

Complete installation and configuration guide for GitHub AI Agents.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Agent Configuration](#agent-configuration)
- [GitHub Configuration](#github-configuration)
- [Security Setup](#security-setup)
- [Verification](#verification)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python 3.11 or higher**
  ```bash
  python --version  # Should show 3.11.x or higher
  ```

- **Git**
  ```bash
  git --version
  ```

- **GitHub CLI (gh)**
  ```bash
  gh --version
  ```
  Install from: https://cli.github.com/

### Optional Software

- **Docker** (for containerized deployment)
  ```bash
  docker --version
  docker-compose --version
  ```

- **Node.js 22+** (for Claude CLI, optional)
  ```bash
  node --version  # Should show 22.x or higher if using Claude
  ```

### Access Requirements

- GitHub account with repository access
- GitHub personal access token with `repo` scope
- At least one AI agent API key (OpenRouter, Anthropic, or Google)

## Installation Methods

### Method 1: Development Installation (Recommended)

Best for: Active development and contributions

```bash
# Clone repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Install package in editable mode
pip install -e packages/github_ai_agents

# Install with development dependencies
pip install -e "packages/github_ai_agents[dev]"
```

**Verify installation:**
```bash
which issue-monitor  # Should return path to executable
issue-monitor --help
```

### Method 2: Production Installation

Best for: Stable deployments without development tools

```bash
# Install directly from GitHub
pip install git+https://github.com/AndrewAltimit/template-repo.git#subdirectory=packages/github_ai_agents
```

### Method 3: Docker Installation

Best for: Containerized deployments and CI/CD

```bash
# Clone repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Run issue monitor in a container, installing the package first
# Note: Must combine install + run in single command since containers are ephemeral
docker-compose run --rm \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -e GITHUB_REPOSITORY=$GITHUB_REPOSITORY \
  -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  python-ci bash -c "pip install -e packages/github_ai_agents && issue-monitor"
```

### Method 4: GitHub Actions (Self-Hosted Runner)

Best for: Automated monitoring in production

See [GitHub Actions Configuration](#github-actions-configuration) section below.

## Agent Configuration

Configure at least one AI agent. You can use multiple agents simultaneously.

### OpenCode & Crush (Recommended for Getting Started)

**Advantages:** Easy setup, pay-as-you-go pricing, no subscription required

1. **Get API Key:**
   - Visit https://openrouter.ai/keys
   - Create account and generate API key

2. **Set Environment Variable:**
   ```bash
   export OPENROUTER_API_KEY=your_api_key_here

   # Add to shell profile for persistence
   echo 'export OPENROUTER_API_KEY=your_api_key_here' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Verify:**
   ```bash
   echo $OPENROUTER_API_KEY  # Should print your key
   ```

### Claude (Requires Claude Pro Subscription)

**Advantages:** High-quality code generation, best for complex tasks

1. **Prerequisites:**
   - Claude Pro subscription
   - Node.js 22+

2. **Install Claude CLI:**
   ```bash
   # Install globally
   npm install -g @anthropic-ai/claude-code

   # Or use repository helper
   ./tools/cli/agents/run_claude.sh --help
   ```

3. **Authenticate:**
   ```bash
   claude-code auth
   # Follow browser authentication flow
   ```

4. **Verify:**
   ```bash
   claude-code --version
   ```

**Note:** Claude runs on the host (not in containers) due to authentication requirements. See `docs/ai-agents/claude-auth.md` for details.

### Gemini (Optional)

**Advantages:** Free tier available, good for code review

1. **Get API Key:**
   - Visit https://makersuite.google.com/app/apikey
   - Create API key

2. **Set Environment Variable:**
   ```bash
   export GEMINI_API_KEY=your_api_key_here

   # Add to shell profile
   echo 'export GEMINI_API_KEY=your_api_key_here' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Install Gemini CLI (Optional):**
   ```bash
   # Install package dependencies
   pip install -e packages/github_ai_agents[all]

   # Or use containerized version
   ./tools/cli/containers/run_gemini_container.sh
   ```

### Codex (Optional, Experimental)

**Advantages:** AI-powered code completion

1. **Install Codex CLI:**
   ```bash
   npm install -g @openai/codex
   ```

2. **Authenticate:**
   ```bash
   codex auth  # Creates ~/.codex/auth.json
   ```

3. **Verify:**
   ```bash
   codex --version
   ```

## GitHub Configuration

### Personal Access Token

1. **Create Token:**
   - Visit https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes:
     - `repo` - Full control of private repositories
     - `write:discussion` - Read and write discussions (optional)
   - Generate and copy token

2. **Set Environment Variable:**
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here

   # Add to shell profile
   echo 'export GITHUB_TOKEN=ghp_your_token_here' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Set Repository:**
   ```bash
   export GITHUB_REPOSITORY=owner/repo

   # Add to shell profile
   echo 'export GITHUB_REPOSITORY=owner/repo' >> ~/.bashrc
   source ~/.bashrc
   ```

### GitHub CLI Authentication

Authenticate GitHub CLI for additional operations:

```bash
gh auth login
# Follow interactive prompts
```

**Verify:**
```bash
gh auth status
```

## Security Setup

### User Authorization Allow List

Create security configuration to control who can trigger agents:

1. **Create Configuration File:**
   ```bash
   # Create .github directory if it doesn't exist
   mkdir -p .github

   # Create security configuration
   cat > .github/ai-agents-security.yml <<EOF
   # GitHub AI Agents Security Configuration
   allowed_users:
     - your-github-username
     - collaborator-username

   # Optional: Configure rate limiting
   rate_limiting:
     enabled: true
     max_requests_per_hour: 10
   EOF
   ```

2. **Commit Configuration:**
   ```bash
   git add .github/ai-agents-security.yml
   git commit -m "Configure AI agents security"
   git push
   ```

See [Security Documentation](security.md) for complete security features.

### Repository Validation

Configure which repositories agents can access:

```bash
# Set allowed repository
export GITHUB_REPOSITORY=owner/repo

# Or in security config (.github/ai-agents-security.yml)
allowed_repositories:
  - owner/repo1
  - owner/repo2
```

## Verification

### Test Installation

```bash
# Check package installation
python -c "from github_ai_agents.monitors import IssueMonitor; print('Success')"

# Check CLI tools
issue-monitor --help
pr-monitor --help

# Check environment variables
echo $GITHUB_TOKEN        # Should show token
echo $GITHUB_REPOSITORY   # Should show repo
echo $OPENROUTER_API_KEY  # Should show key (if using OpenRouter)
```

### Test Agent Availability

```bash
# Test with Python
python -c "
from github_ai_agents.agents import get_available_agents
agents = get_available_agents()
print(f'Available agents: {[a.name for a in agents]}')
"
```

### Run Test Suite

```bash
# Run unit tests (fast)
pytest packages/github_ai_agents/tests/unit -v

# Run integration tests
pytest packages/github_ai_agents/tests/integration -v

# Run all tests with coverage
pytest packages/github_ai_agents/tests/ -v --cov=github_ai_agents
```

### Create Test Issue

```bash
# Create test issue to verify end-to-end functionality
gh issue create \
  --title "Test: AI Agent Setup" \
  --body "Please create a simple hello world function.

[Approved][OpenCode]"

# Run issue monitor
issue-monitor

# Check for created PR
gh pr list
```

## Advanced Configuration

### Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GITHUB_TOKEN` | Yes | GitHub personal access token | `ghp_abc123...` |
| `GITHUB_REPOSITORY` | Yes | Target repository | `owner/repo` |
| `OPENROUTER_API_KEY` | Conditional | OpenRouter API key (for OpenCode/Crush) | `sk-or-v1-abc...` |
| `ANTHROPIC_API_KEY` | Conditional | Anthropic API key (optional, CLI is primary) | `sk-ant-abc...` |
| `GEMINI_API_KEY` | Conditional | Google Gemini API key | `AIza...` |

### Configuration Files

#### Package Configuration (`pyproject.toml`)

Located at: `packages/github_ai_agents/pyproject.toml`

**Key settings:**
- Python version: `>=3.11`
- Dependencies: See `[project.dependencies]`
- Optional features: `[project.optional-dependencies]`

#### Security Configuration (`.github/ai-agents-security.yml`)

**Example:**
```yaml
# User authorization
allowed_users:
  - admin-user
  - developer-1

# Repository validation
allowed_repositories:
  - owner/repo1
  - owner/repo2

# Rate limiting
rate_limiting:
  enabled: true
  max_requests_per_hour: 10
  max_requests_per_day: 100

# Agent-specific settings
agents:
  claude:
    enabled: true
  opencode:
    enabled: true
  gemini:
    enabled: false
```

### GitHub Actions Configuration

**Self-Hosted Runner Setup:**

1. **Install Runner:**
   ```bash
   # Follow GitHub's instructions for self-hosted runners
   # Settings → Actions → Runners → New self-hosted runner
   ```

2. **Create Workflow:**
   ```yaml
   # .github/workflows/ai-agents-monitor.yml
   name: AI Agents Monitor

   on:
     schedule:
       - cron: '0 * * * *'  # Every hour
     workflow_dispatch:

   jobs:
     issue-monitor:
       runs-on: self-hosted
       steps:
         - uses: actions/checkout@v4

         - name: Run issue monitor in container
           env:
             GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
             GITHUB_REPOSITORY: ${{ github.repository }}
             OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
           run: |
             docker-compose run --rm \
               -e GITHUB_TOKEN \
               -e GITHUB_REPOSITORY \
               -e OPENROUTER_API_KEY \
               python-ci bash -c "\
                 pip install -e packages/github_ai_agents && \
                 issue-monitor"
   ```

3. **Add Secrets:**
   - Go to repository Settings → Secrets and variables → Actions
   - Add `OPENROUTER_API_KEY` (or other agent API keys)

### Docker Compose Configuration

**Custom docker-compose.yml:**

```yaml
version: '3.8'

services:
  issue-monitor:
    image: python:3.11-slim
    volumes:
      - ./packages/github_ai_agents:/app
    working_dir: /app
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_REPOSITORY=${GITHUB_REPOSITORY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    command: >
      bash -c "
        pip install -e . &&
        issue-monitor --continuous --interval 300
      "
```

**Run with:**
```bash
docker-compose up issue-monitor
```

## Troubleshooting

### Common Installation Issues

#### Python Version Mismatch

**Problem:** Error about Python version < 3.11

**Solution:**
```bash
# Check Python version
python --version

# Install Python 3.11+ if needed (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11

# Use specific Python version
python3.11 -m pip install -e packages/github_ai_agents
```

#### Missing GitHub CLI

**Problem:** `gh: command not found`

**Solution:**
```bash
# Install GitHub CLI (Ubuntu/Debian)
sudo apt install gh

# Or download from
# https://cli.github.com/
```

#### Permission Denied on pip install

**Problem:** Permission error during pip install

**Solution:**
```bash
# Use user install (no sudo)
pip install --user -e packages/github_ai_agents

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install -e packages/github_ai_agents
```

### Common Configuration Issues

#### Environment Variables Not Persisting

**Problem:** Variables reset after closing terminal

**Solution:**
```bash
# Add to shell profile
echo 'export GITHUB_TOKEN=your_token' >> ~/.bashrc
echo 'export GITHUB_REPOSITORY=owner/repo' >> ~/.bashrc
echo 'export OPENROUTER_API_KEY=your_key' >> ~/.bashrc

# Reload profile
source ~/.bashrc
```

#### Token Permissions Insufficient

**Problem:** Error about missing permissions

**Solution:**
1. Go to https://github.com/settings/tokens
2. Click on your token
3. Ensure `repo` scope is checked
4. Regenerate token if needed
5. Update `GITHUB_TOKEN` environment variable

#### Agent Not Available

**Problem:** Agent shows as not available

**Solution:**
```bash
# Check API key is set
echo $OPENROUTER_API_KEY  # Or appropriate variable

# Verify API key is valid
# Test with a simple API call using curl or agent CLI

# Check network connectivity
ping api.openrouter.ai
```

### Docker-Specific Issues

#### Permission Denied in Container

**Problem:** Cannot write files in mounted volumes

**Solution:**
```bash
# Run with user ID
docker-compose run --rm -u $(id -u):$(id -g) python-ci issue-monitor
```

#### Container Cannot Access Credentials

**Problem:** API keys not available in container

**Solution:**
```bash
# Pass environment variables explicitly
docker-compose run --rm \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  python-ci issue-monitor
```

## Next Steps

After installation:

1. **Quick Start:** Follow [QUICK_START.md](QUICK_START.md) to test your setup
2. **Security:** Review [security.md](security.md) for production deployment
3. **Architecture:** Read [architecture.md](architecture.md) to understand the system
4. **Examples:** Check `examples/` directory for usage patterns *(coming in v0.2.0)*

## Getting Help

- **Documentation Index:** [INDEX.md](INDEX.md)
- **Testing Guide:** [../tests/README.md](../tests/README.md)
- **GitHub Issues:** https://github.com/AndrewAltimit/template-repo/issues

---

**Installation complete!** You're ready to start using GitHub AI Agents.
