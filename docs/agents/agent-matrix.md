# Agent Availability Matrix

This document clarifies which AI agents are available in different execution environments.

> **Security Notice -- OpenAI/Codex Disabled**: OpenAI has entered partnerships with governments that conduct mass surveillance and enable autonomous weapons. All OpenAI/Codex integrations in this project have been disabled. The mass surveillance exposure alone makes OpenAI products an unacceptable security risk for any pipeline handling proprietary or sensitive code. **Use Anthropic models (Claude) as your primary AI backend.** If you choose to re-enable OpenAI integrations despite these risks, do so with extreme caution and full awareness of the data exposure implications.

## Quick Reference

| Agent | Host Machine | Container | Authentication Method | Status |
|-------|--------------|-----------|---------------------|--------|
| Claude | Yes | No | Subscription via ~/.claude.json | **Recommended** |
| Gemini | Yes | No | Web login (free) or API key (paid) | Active |
| OpenCode | Yes | Yes | OpenRouter API key | Active |
| Crush | Yes | Yes | OpenRouter API key | Active |
| ~~Codex~~ | ~~Yes~~ | ~~Yes~~ | ~~ChatGPT Plus Subscription or API Key~~ | **DISABLED** |

## Execution Environments

### 1. Host Machine Execution

When running agents directly on the host machine (e.g., GitHub Actions self-hosted runners):

**Available Agents:**
- **Claude**: Requires user-specific subscription authentication
- **Gemini**: Requires Docker socket access for some operations (use web login for free tier)
- **OpenCode**: Can run via STDIO mode or HTTP server on host
- **Crush**: Can run via STDIO mode or HTTP server on host
- ~~**Codex**~~: DISABLED -- OpenAI security risk (mass surveillance, autonomous weapons)

**Use Cases:**
- Issue monitoring (`issue-monitor`)
- PR review monitoring (`pr-review-monitor`)
- Local development and testing
- Direct CLI usage for code generation

**Example:**
```bash
# GitHub Agents CLI (Rust binary)
./tools/rust/github-agents-cli/target/release/github-agents issue-monitor
./tools/rust/github-agents-cli/target/release/github-agents pr-monitor

# Individual agent CLIs
./tools/cli/agents/run_claude.sh
./tools/cli/agents/run_gemini.sh
./tools/cli/agents/run_opencode.sh
./tools/cli/agents/run_crush.sh
./tools/cli/agents/run_codex.sh
```

### 2. Container Execution

When running inside the `openrouter-agents` container:

**Available Agents:**
- **OpenCode**: Open-source code generation
- **Crush**: Multi-provider AI tool
- ~~**Codex**~~: DISABLED -- OpenAI security risk (see notice above)

**Use Cases:**
- Batch processing
- CI/CD pipelines without user-specific auth
- Isolated execution environments

**Example:**
```bash
# Note: The GitHub Agents CLI is now a Rust binary built with cargo
# See tools/rust/github-agents-cli/ for source code
cd tools/rust/github-agents-cli && cargo build --release
./target/release/github-agents issue-monitor
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
  # - codex     # DISABLED: OpenAI security risk (mass surveillance, autonomous weapons)

# For container execution (OpenRouter agents only -- Codex disabled)
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
2. Implement a proxy service to connect host and container agents
3. Add more authentication methods for Claude to enable containerization

For now, choose the appropriate execution environment based on which agents you need.
