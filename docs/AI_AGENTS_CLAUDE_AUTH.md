# Claude Authentication in AI Agents

## Why AI Agents Run on Host Machine

The AI agents (issue monitor and PR review monitor) run directly on the host machine instead of in Docker containers. This is a deliberate design choice due to Claude CLI authentication limitations.

### The Authentication Problem

Claude CLI subscription authentication (obtained via `claude login`) is tied to the specific machine and user session where the login was performed. The authentication tokens stored in `~/.claude.json` are not portable to other environments, particularly containers.

When you try to use these credentials in a container, you'll see:
```
Invalid API key · Please run /login
```

### Why This Happens

1. **Session-based Auth**: Claude subscription authentication creates session tokens that are machine-specific
2. **Container Isolation**: Containers run in isolated environments with different system characteristics
3. **Security Design**: This is likely by design to prevent credential sharing across different environments

### Our Solution: Host Execution

We've modified the GitHub Actions workflows to run the AI agents directly on the self-hosted runner machine instead of in containers. This allows the agents to:

1. Access the host's `~/.claude.json` authentication file
2. Use the same environment where `claude login` was performed
3. Maintain the security context that Claude CLI expects

### Implications of Host Execution

Running on the host machine means:

1. **Python Dependencies**: Must be installed on the host with `pip3 install --user`
2. **Claude CLI Required**: Must be installed on the host machine
3. **Less Isolation**: The agents run with the same permissions as the runner user
4. **Environment Consistency**: The host must maintain consistent Python and tool versions

### Setup Requirements

For the AI agents to work on your self-hosted runner:

1. **Install nvm and Node.js 22.16.0**:
   - Claude CLI requires Node.js 22.16.0 specifically
   - Install nvm, then run `nvm install 22.16.0`
2. **Install Claude CLI**:
   - First run `nvm use 22.16.0`
   - Then `npm install -g @anthropic-ai/claude-code`
3. **Authenticate Claude**:
   - Run `nvm use 22.16.0` first
   - Then `claude login` on the host machine
4. **Install Python Dependencies**: The workflows will attempt to install required packages
5. **GitHub CLI**: Must be available on the host (usually pre-installed on runners)

### Quick Setup

We provide a setup script to help prepare your host machine:

```bash
# Run from the project root directory
./scripts/setup-host-for-agents.sh
```

This script will:
- Check for required tools (Python, pip, Claude CLI, GitHub CLI)
- Verify authentication status
- Install Python dependencies with `pip3 install --user`
- Provide guidance for any missing components

## Potential Solutions

### 1. Use API Keys Instead (Recommended for CI/CD)

If you have access to Anthropic API keys, you can:
- Set `ANTHROPIC_API_KEY` environment variable
- This works across all environments including containers
- More suitable for automated/CI environments

### 2. Run on Self-Hosted Runners

If you're using self-hosted GitHub Actions runners on the same machine where you use Claude:
- The agents could potentially run outside containers
- Direct access to host's `~/.claude.json`
- Requires modifying workflows to not use Docker

### 3. Wait for CI/CD Authentication Support

Claude CLI mentions a `setup-token` command that might support long-lived tokens for CI/CD, but this feature may not be fully available yet.

## Workaround for Now

Until a proper solution is available, you can:

1. **Manual Trigger**: Run the agents locally on your development machine
2. **Self-Hosted Runner**: Configure workflows to run directly on host (not in containers)
3. **API Key**: Switch to using Anthropic API keys if available

## Future Improvements

We should monitor Claude CLI updates for:
- Long-lived token support for CI/CD
- Portable authentication methods
- Official guidance for containerized environments
