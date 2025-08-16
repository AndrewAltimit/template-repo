# Agent Availability Matrix

This document clarifies which AI agents are available in different execution environments.

## Quick Reference

| Agent | Host Machine | Container | Authentication Method |
|-------|--------------|-----------|---------------------|
| Claude | ✅ | ❌ | Subscription via ~/.claude.json |
| Gemini | ✅ | ❌ | API key + Docker socket access |
| OpenCode | ❌ | ✅ | OpenRouter API key |
| Crush | ❌ | ✅ | OpenRouter API key |

## Execution Environments

### 1. Host Machine Execution

When running agents directly on the host machine (e.g., GitHub Actions self-hosted runners):

**Available Agents:**
- **Claude**: Requires user-specific subscription authentication
- **Gemini**: Requires Docker socket access for some operations

**Use Cases:**
- Issue monitoring (`issue-monitor`)
- PR review monitoring (`pr-review-monitor`)
- Local development and testing

**Example:**
```bash
python3 -m github_ai_agents.cli issue-monitor
```

### 2. Container Execution

When running inside the `openrouter-agents` container:

**Available Agents:**
- **OpenCode**: Open-source code generation
- **Crush**: Multi-provider AI tool

**Use Cases:**
- Batch processing
- CI/CD pipelines without user-specific auth
- Isolated execution environments

**Example:**
```bash
docker-compose run --rm openrouter-agents python -m github_ai_agents.cli issue-monitor
```

## Configuration

The `.agents.yaml` file should only enable agents available in your execution environment:

```yaml
# For host execution (default)
enabled_agents:
  - claude
  - gemini

# For container execution
# enabled_agents:
#   - opencode
#   - crush
```

## Error Handling

When an agent is requested but not available in the current environment, you'll see:

```
Agent 'OpenCode' is only available in the containerized environment.

This agent runs in the `openrouter-agents` Docker container and is not available
when the issue monitor runs on the host (required for Claude authentication).

Available host agents: ['claude', 'gemini']
```

## Why This Design?

1. **Authentication Constraints**: Claude requires user-specific subscription auth that can't be easily containerized
2. **Security**: Gemini needs Docker socket access, which is risky to expose in containers
3. **Isolation**: OpenRouter agents are fully containerized for better security and portability
4. **Flexibility**: Different agents for different use cases and environments

## Future Improvements

We're exploring options to:
1. Create a hybrid execution model where host agents can delegate to containerized agents
2. Implement a proxy service to bridge host and container agents
3. Add more authentication methods for Claude to enable containerization

For now, choose the appropriate execution environment based on which agents you need.
