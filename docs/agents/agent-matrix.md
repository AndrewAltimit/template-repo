# Agent Availability Matrix

This is the canonical agent roster for the repository. Other documents give a short list and link here.

## Quick Reference

| Agent | Host Machine | Container | Authentication Method | Status |
|-------|--------------|-----------|---------------------|--------|
| Claude | Yes | No | Subscription via ~/.claude.json | **Primary** (development, PR security + quality reviews) |
| OpenRouter | Yes | Yes | OpenRouter API key | Active (PR general review, `qwen/qwen3.7-max`) |
| OpenCode | Yes | Yes | OpenRouter API key | Active |
| Crush | Yes | Yes | OpenRouter API key | Active |
| GitHub Copilot | n/a | n/a | GitHub | Active (review suggestions in the PR UI) |
| Gemini | n/a | n/a | n/a | **Legacy / not allowed** |
| Codex | n/a | n/a | n/a | **Legacy / not allowed** |

The automated PR review pipeline (`.github/workflows/pr-validation.yml`) runs Claude security review, Claude quality review, and OpenRouter general review in parallel, with an optional AgentCore review when the `agentcore-review` label is applied. Profiles live in `review-profiles.yaml`; the enabled agents and review priorities live in `.agents.yaml`.

## Legacy Agents: Gemini and Codex (Not Allowed)

Google Gemini and OpenAI Codex integrations remain in the repository as legacy code (`tools/mcp/mcp_gemini/`, `tools/mcp/mcp_codex/`, `tools/cli/agents/run_gemini.sh`, `tools/cli/agents/run_codex.sh`, related docs). They are **not allowed in the lab**: unsupported, not enabled in `.agents.yaml`, and not to be enabled or used.

- **Gemini (Google)**: on February 4, 2025 Google removed from its AI Principles the pledge not to pursue AI for weapons or for surveillance that violates internationally accepted norms.
- **Codex (OpenAI)**: OpenAI is partnering with governments that conduct mass surveillance and enable autonomous weapons. The surveillance exposure alone makes it unacceptable for pipelines handling proprietary or sensitive code.

Documents that still describe these integrations carry a "Legacy / not allowed" marker linking to this section. Use Anthropic models (Claude) as the primary AI backend.

## Execution Environments

### 1. Host Machine Execution

When running agents directly on the host machine (e.g., GitHub Actions self-hosted runners):

**Available Agents:**
- **Claude**: Requires user-specific subscription authentication
- **OpenCode**: Can run via STDIO mode or HTTP server on host
- **Crush**: Can run via STDIO mode or HTTP server on host

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
cd tools/rust/github-agents-cli && cargo build --release
./target/release/github-agents issue-monitor
```

## Configuration

`.agents.yaml` enables agents based on the execution environment and available authentication. The current file enables:

```yaml
enabled_agents:
  - claude      # Host-only, subscription auth
  - opencode    # Runs in the openrouter-agents container
  - crush       # Runs in the openrouter-agents container
  - openrouter  # API-based, no CLI required
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
2. **Flexibility**: OpenRouter agents (OpenCode, Crush) can run both on host and in containers
3. **Cost**: OpenRouter agents use pay-per-use API keys; Claude uses the existing subscription
