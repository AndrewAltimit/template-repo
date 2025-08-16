# Autonomous Mode for AI Agents in CI/CD

This document explains the autonomous mode configuration required for AI agents to operate in CI/CD environments.

## Overview

All AI agents in this system are configured to run in **fully autonomous mode** for CI/CD automation. This means:

- No human interaction is required or possible
- All interactive prompts are disabled
- Agents run in sandboxed environments for security
- Permission checks are bypassed to enable automation

## Why Autonomous Mode?

In CI/CD environments:
1. **No TTY**: There's no terminal for interactive prompts
2. **Automated Workflows**: GitHub Actions/GitLab CI need unattended execution
3. **Sandboxed Security**: Agents run in isolated containers/VMs
4. **Continuous Operation**: No human available to respond to prompts

## Agent-Specific Configurations

### Claude (Anthropic)
```bash
claude --print --dangerously-skip-permissions --output-format text "prompt"
```
- `--print`: Non-interactive mode, prints response and exits
- `--dangerously-skip-permissions`: Bypasses all permission prompts (REQUIRED for CI/CD)
- `--output-format text`: Plain text output for parsing

### Gemini (Google)
```bash
gemini -m gemini-2.5-pro -p "prompt"
```
- `-m`: Model selection (non-interactive)
- `-p`: Prompt provided as argument (no stdin interaction)

### OpenCode
```bash
opencode --non-interactive --model qwen/qwen-2.5-coder-32b-instruct --input prompt.md
```
- `--non-interactive`: Disables all interactive features
- `--input`: File-based input (no terminal interaction)

### Crush (Charm Bracelet)
```bash
crush --provider openrouter --model qwen/qwen-2.5-coder-32b-instruct --non-interactive --no-update "prompt"
```
- `--non-interactive`: No terminal UI
- `--no-update`: Prevents auto-updates during CI/CD runs

## Security Considerations

### Sandboxed Environments
All agents MUST run in isolated environments:
- Docker containers with limited capabilities
- VMs with restricted network access
- No access to production secrets
- Read-only access to sensitive paths

### Environment Variables
```bash
# Required for autonomous mode
export CLAUDE_AUTONOMOUS_MODE="true"
export AGENT_SANDBOX_MODE="true"

# API Keys (if using API mode)
export ANTHROPIC_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

### Best Practices
1. **Never run autonomous mode on developer workstations**
2. **Always use sandboxed environments**
3. **Rotate API keys regularly**
4. **Monitor agent activity logs**
5. **Set resource limits (CPU, memory, timeout)**

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run AI Agent Task
  env:
    CLAUDE_AUTONOMOUS_MODE: "true"
    AGENT_SANDBOX_MODE: "true"
  run: |
    docker run --rm \
      --memory="1g" \
      --cpus="1" \
      --read-only \
      --network="none" \
      -v ${{ github.workspace }}:/workspace:ro \
      ai-agents:latest \
      python -m github_ai_agents.cli issue-monitor
```

### Docker Security
```dockerfile
# Run as non-root user
USER nonroot:nonroot

# Read-only root filesystem
RUN chmod -R 555 /app

# No new privileges
SECURITY_OPTS="--security-opt=no-new-privileges"
```

## Troubleshooting

### Agent Hangs or Timeouts
- Check for missing non-interactive flags
- Verify no TTY allocation (`-t` flag in docker)
- Ensure timeout limits are set

### Permission Errors
- Verify `--dangerously-skip-permissions` for Claude
- Check file permissions in containers
- Ensure API keys are properly set

### Output Parsing Issues
- Use `--output-format text` for consistent output
- Strip ANSI escape codes
- Handle partial output on timeouts

## Testing Autonomous Mode

Test agents in CI-like environment:
```bash
# No TTY allocation
docker run --rm ai-agents python -c "
import subprocess
result = subprocess.run(
    ['claude', '--print', '--dangerously-skip-permissions', 'test'],
    capture_output=True,
    text=True,
    timeout=30
)
print(f'Exit code: {result.returncode}')
print(f'Output: {result.stdout}')
"
```

## Integration with GitHub AI Agents

When using the `github_ai_agents` package, the monitors automatically configure agents for autonomous mode:

```python
from github_ai_agents.agents import ClaudeAgent

# The agent class handles autonomous mode configuration internally
agent = ClaudeAgent()
response = await agent.generate_code(
    prompt="Implement the feature",
    context={"autonomous": True}
)
```

## Conclusion

Autonomous mode is essential for AI agents in CI/CD. While flags like `--dangerously-skip-permissions` may seem risky, they're necessary and safe when:
1. Running in properly sandboxed environments
2. Following security best practices
3. Monitoring agent activity
4. Using resource limits

The key is isolation - agents should never have access to sensitive production systems when running in autonomous mode.
