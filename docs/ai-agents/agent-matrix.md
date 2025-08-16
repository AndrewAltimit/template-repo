# Agent Availability Matrix

This document clarifies which AI agents are available in different execution environments.

## Quick Reference

| Agent | Host Machine | Container | Authentication Method |
|-------|--------------|-----------|---------------------|
| Claude | ✅ | ❌ | Subscription via ~/.claude.json |
| Gemini | ✅ | ❌ | Web login (free) or API key (paid) + Docker socket |
| OpenCode | ✅ | ✅ | OpenRouter API key |
| Crush | ✅ | ✅ | OpenRouter API key |

## Execution Environments

### 1. Host Machine Execution

When running agents directly on the host machine (e.g., GitHub Actions self-hosted runners):

**Available Agents:**
- **Claude**: Requires user-specific subscription authentication
- **Gemini**: Requires Docker socket access for some operations (use web login for free tier)
- **OpenCode**: Can run via STDIO mode or HTTP server on host
- **Crush**: Can run via STDIO mode or HTTP server on host

**Use Cases:**
- Issue monitoring (`issue-monitor`)
- PR review monitoring (`pr-review-monitor`)
- Local development and testing
- Direct CLI usage for code generation

**Example:**
```bash
python3 -m github_ai_agents.cli issue-monitor
./tools/cli/agents/run_opencode.sh
./tools/cli/agents/run_crush.sh
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

The `.agents.yaml` file should enable agents based on your execution environment and available authentication:

```yaml
# For host execution with all agents
enabled_agents:
  - claude      # Requires subscription auth
  - gemini      # Free with web login, paid with API key
  - opencode    # Requires OpenRouter API key
  - crush       # Requires OpenRouter API key

# For container execution (OpenRouter agents only)
# enabled_agents:
#   - opencode
#   - crush
```

## Error Handling

When an agent is requested but not available in the current environment, you'll see:

```
Agent 'Claude' is not available in the current environment.

This agent requires specific authentication that may not be configured.
Please check your authentication setup and .agents.yaml configuration.

Available agents: [list of configured agents]
```

## Why This Design?

1. **Authentication Constraints**: Claude requires user-specific subscription auth that can't be easily containerized
2. **Security**: Gemini needs Docker socket access, which is risky to expose in containers
3. **Flexibility**: OpenRouter agents (OpenCode, Crush) can run both on host and in containers for maximum flexibility
4. **Cost Optimization**: Gemini uses free tier with web login, OpenRouter agents use pay-per-use API keys
5. **Multiple Options**: Different agents for different use cases and environments

## Future Improvements

We're exploring options to:
1. Create a hybrid execution model where host agents can delegate to containerized agents
2. Implement a proxy service to bridge host and container agents
3. Add more authentication methods for Claude to enable containerization

For now, choose the appropriate execution environment based on which agents you need.
