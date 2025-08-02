# Multi-Agent Feature: Key Findings & Decisions

## Executive Summary

After researching OpenCode, Codex CLI, and Crush, we discovered all three are **terminal-based CLI tools** rather than API services. This fundamentally changes our integration approach from HTTP APIs to subprocess management.

## Key Discoveries

### 1. Tool Nature
- **OpenCode**: Terminal UI agent with 75+ LLM provider support
- **Codex CLI**: New OpenAI terminal tool (original Codex API deprecated March 2023)
- **Crush**: Charm Bracelet's CLI with MCP protocol support

### 2. Integration Challenges
- All tools designed for **interactive human use**
- No native API endpoints for programmatic access
- Output includes terminal formatting (ANSI codes, TUI elements)
- Authentication varies per tool (config files, env vars, login commands)

### 3. OpenRouter.ai Compatibility
- ✅ **OpenCode**: Native support via Models.dev integration
- ⚠️ **Codex CLI**: Primarily OpenAI, but may support custom endpoints
- ✅ **Crush**: Full support for OpenRouter and multiple providers

## Architectural Decisions

### 1. CLI Wrapper Pattern
Instead of HTTP clients, we'll create subprocess wrappers:
```python
class CLIAgentWrapper(AIAgent):
    async def generate_code(prompt, context):
        # Spawn subprocess
        # Send input via stdin or temp files
        # Parse output from stdout
        # Handle timeouts and errors
```

### 2. Host-Based Execution
Like Claude Code and our AI agents, these tools will run on the host:
- No containerization (tools expect filesystem access)
- Binary management via package managers
- Environment-based configuration

### 3. Non-Interactive Mode
We'll need to:
- Use flags like `--non-interactive` where available
- Create input files instead of interactive prompts
- Parse structured output (JSON) when possible
- Strip terminal formatting from outputs

## Revised Architecture

```
GitHub Issue/PR
    ↓
Agent Selector (based on [Trigger])
    ↓
CLI Agent Wrapper
    ↓
Subprocess Execution
    ├── OpenCode binary
    ├── Codex CLI (npm)
    └── Crush binary
    ↓
Output Parser
    ↓
Response to GitHub
```

## Implementation Priority

1. **Phase 1**: Build robust CLI wrapper infrastructure
2. **Phase 2**: Implement OpenCode (most mature, best OpenRouter support)
3. **Phase 3**: Add Crush (good multi-provider support)
4. **Phase 4**: Evaluate Codex CLI (depends on OpenRouter compatibility)

## Critical Success Factors

1. **Reliable subprocess management** with timeouts and error handling
2. **Flexible authentication** supporting multiple methods per tool
3. **Smart output parsing** to extract code from terminal UIs
4. **Graceful fallbacks** when tools are unavailable
5. **Clear documentation** on tool installation and configuration

## Next Steps

1. Prototype the CLI wrapper with one tool (recommend OpenCode)
2. Test non-interactive modes and output parsing
3. Implement authentication management
4. Create installation scripts for all tools
5. Build comprehensive test suite for subprocess handling

## Risk Assessment

- **High Risk**: Tools change CLI interfaces in updates
- **Medium Risk**: Subprocess overhead impacts performance
- **Medium Risk**: Terminal output parsing complexity
- **Low Risk**: OpenRouter.ai integration (2/3 tools support it)

## Recommendation

Proceed with the multi-agent feature but adjust expectations:
- These are **automation wrappers** around interactive tools
- Not as clean as API integrations
- May require ongoing maintenance as tools evolve
- Consider contributing non-interactive modes upstream
