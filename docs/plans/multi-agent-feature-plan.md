# Multi-Agent Feature Plan

## Overview

This feature will expand the template repository's AI agent ecosystem from 2 agents (Claude Code, Gemini CLI) to 5 agents by adding:
- **OpenCode** (SST's open-source terminal-based AI coding agent)
- **Codex CLI** (OpenAI's new terminal-based coding agent, not the deprecated API)
- **Crush** (Charm Bracelet's terminal-based AI coding assistant)

Users will be able to pick and choose which agents they want to use, with all new agents supporting OpenRouter.ai for model flexibility.

**Important Update**: All three new agents are terminal-based CLI tools (like Claude Code), not API services. This requires a different integration approach using subprocess calls rather than HTTP APIs.

## Current State

### Existing Agents
1. **Claude Code** (Anthropic)
   - Model: Opus 4
   - Auth: Claude subscription
   - Trigger: `[Claude]`
   - Use: Primary development assistant

2. **Gemini CLI** (Google)
   - Model: 2.5 Pro (fallback to 2.5 Flash)
   - Auth: API key
   - Trigger: `[Gemini]`
   - Use: Code reviews, second opinions

### Existing Infrastructure
- **Issue Monitor Agent**: Creates PRs from well-described issues
- **PR Review Monitor Agent**: Implements fixes based on review feedback
- **Security Model**: Keyword triggers, allow list, commit validation
- **CI/CD**: Self-hosted GitHub Actions

## Proposed Architecture

### 1. Agent Abstraction Layer

Create a unified interface for all agents:

```python
# scripts/agents/core/agent_interface.py
class AIAgent(ABC):
    @abstractmethod
    async def generate_code(self, prompt: str, context: dict) -> str:
        pass

    @abstractmethod
    async def review_code(self, code: str, instructions: str) -> str:
        pass

    @abstractmethod
    def get_trigger_keyword(self) -> str:
        pass

    @abstractmethod
    def get_model_config(self) -> dict:
        pass
```

### 2. New Agent Implementations

#### OpenCode Agent
- **Trigger**: `[OpenCode]`
- **Default Model**: qwen/qwen-2.5-coder-32b-instruct (via OpenRouter)
- **Features**:
  - Terminal UI with multi-session support
  - LSP integration for code understanding
  - 75+ LLM provider support via Models.dev
  - Plan mode for feature planning
- **Installation**: `curl -fsSL https://opencode.ai/install | bash` or `npm i -g opencode-ai@latest`
- **Interface**: CLI subprocess calls with stdin/stdout communication

#### Codex CLI Agent
- **Trigger**: `[Codex]`
- **Default Model**: gpt-4 (requires OpenAI API key)
- **Alternative**: qwen/qwen-2.5-coder-32b-instruct (via OpenRouter if configured)
- **Features**:
  - Interactive terminal-based code generation
  - Multimodal support (screenshots/diagrams)
  - Sandboxed command execution
  - Code refactoring and explanation
- **Installation**: `npm i -g @openai/codex` or `brew install codex`
- **Interface**: CLI subprocess with structured prompts

#### Crush Agent
- **Trigger**: `[Crush]`
- **Default Model**: qwen/qwen-2.5-coder-32b-instruct (via OpenRouter)
- **Features**:
  - Multi-model support with context preservation
  - MCP (Model Context Protocol) server support
  - LSP integration
  - Session-based architecture
- **Installation**: `go install github.com/charmbracelet/crush@latest` or platform binaries
- **Interface**: CLI with configuration file support

### 3. OpenRouter.ai Integration

```yaml
# config/agents/openrouter.yaml
openrouter:
  api_key: ${OPENROUTER_API_KEY}
  default_model: qwen/qwen-2.5-coder-32b-instruct
  fallback_models:
    - deepseek/deepseek-coder-v2-instruct
    - meta-llama/llama-3.1-70b-instruct

  agent_overrides:
    opencode:
      model: qwen/qwen-2.5-coder-32b-instruct
      temperature: 0.2
    codex:
      model: qwen/qwen-2.5-coder-32b-instruct
      temperature: 0.3
    crush:
      model: qwen/qwen-2.5-coder-32b-instruct
      temperature: 0.1
```

### 4. CLI Integration Strategy

Since all new agents are terminal-based tools, we need a robust subprocess management system:

```python
# scripts/agents/core/cli_agent_wrapper.py
class CLIAgentWrapper(AIAgent):
    def __init__(self, agent_name: str, config: dict):
        self.agent_name = agent_name
        self.executable = config['executable']
        self.args_template = config['args_template']
        self.timeout = config.get('timeout', 300)

    async def generate_code(self, prompt: str, context: dict) -> str:
        # Prepare command based on agent type
        cmd = self._build_command(prompt, context)

        # Execute with timeout and capture output
        result = await self._execute_with_timeout(cmd)

        # Parse agent-specific output format
        return self._parse_output(result)

    async def _execute_with_timeout(self, cmd: list) -> str:
        """Execute CLI command with proper timeout and error handling"""
        # Implementation with asyncio.subprocess
```

### 5. Example CLI Integration

Here's how we might integrate OpenCode as a concrete example:

```python
# scripts/agents/implementations/opencode_agent.py
class OpenCodeAgent(CLIAgentWrapper):
    def __init__(self):
        super().__init__(
            agent_name="opencode",
            config={
                'executable': 'opencode',
                'args_template': ['--non-interactive', '--model', '{model}'],
                'timeout': 300,
                'env_vars': {
                    'OPENROUTER_API_KEY': os.environ.get('OPENROUTER_API_KEY'),
                    'OPENCODE_MODEL': 'openrouter/qwen/qwen-2.5-coder-32b-instruct'
                }
            }
        )

    def _build_command(self, prompt: str, context: dict) -> list:
        # Create temporary file with context and prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(f"# Context\n{context.get('code', '')}\n\n# Task\n{prompt}")
            temp_file = f.name

        return [
            self.executable,
            '--non-interactive',
            '--input-file', temp_file,
            '--output-format', 'json',
            '--model', self.config['env_vars']['OPENCODE_MODEL']
        ]

    def _parse_output(self, output: str) -> str:
        # Parse JSON output or fall back to raw text
        try:
            result = json.loads(output)
            return result.get('code', result.get('response', ''))
        except:
            # Strip ANSI codes and extract code blocks
            return self._extract_code_from_terminal_output(output)
```

### 6. Configuration System

```yaml
# .agents.yaml (user configuration)
enabled_agents:
  - claude      # Always included
  - gemini      # Optional
  - opencode    # Optional
  - codex       # Optional
  - crush       # Optional

agent_priorities:
  issue_creation: [claude, opencode]
  pr_reviews: [gemini, codex]
  code_fixes: [claude, crush]

model_overrides:
  opencode:
    model: deepseek/deepseek-coder-v2-instruct
  crush:
    temperature: 0.5
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
1. Create agent abstraction layer
2. Refactor existing Claude/Gemini agents to use new interface
3. Add OpenRouter.ai client with rate limiting
4. Update security model for new triggers

### Phase 2: Agent Integration (Week 2)
1. Implement OpenCode agent
   - Docker container setup
   - API wrapper
   - Test harness
2. Implement Codex agent
   - Python package installation
   - OpenRouter backend
   - Test suite
3. Implement Crush agent
   - Go binary management
   - Terminal interface bridge
   - Integration tests

### Phase 3: Pipeline Integration (Week 3)
1. Update issue monitor to support all agents
2. Update PR review monitor for multi-agent reviews
3. Add agent selection logic based on configuration
4. Implement fallback chains

### Phase 4: Documentation & Testing (Week 4)
1. User documentation for each agent
2. Configuration examples
3. Integration test suite
4. Performance benchmarks

## Security Considerations

### 1. API Key Management
```bash
# Environment variables
OPENROUTER_API_KEY=or-xxx
OPENCODE_CONFIG=/path/to/config
CRUSH_AUTH_TOKEN=xxx
```

### 2. Extended Security Model
- Each agent gets its own trigger keyword
- Maintain existing allow list system
- Add per-agent permissions in allow list
- Rate limiting per agent per user

### 3. Audit Trail
```python
# Enhanced logging
{
    "timestamp": "2025-08-02T12:00:00Z",
    "agent": "opencode",
    "trigger": "[OpenCode]",
    "user": "AndrewAltimit",
    "action": "create_pr",
    "model": "qwen/qwen-2.5-coder-32b-instruct",
    "tokens_used": 1234
}
```

## Configuration Examples

### Minimal Setup (Claude only)
```yaml
enabled_agents:
  - claude
```

### Full Setup (All agents)
```yaml
enabled_agents:
  - claude
  - gemini
  - opencode
  - codex
  - crush

openrouter:
  api_key: ${OPENROUTER_API_KEY}
```

### Specialized Setup (Code review focus)
```yaml
enabled_agents:
  - claude     # Primary development
  - gemini     # PR reviews
  - codex      # Additional review perspective

agent_priorities:
  pr_reviews: [gemini, codex]
  issue_creation: [claude]
```

## Migration Strategy

1. **Backward Compatibility**: Existing [Claude] and [Gemini] triggers continue working
2. **Opt-in Adoption**: New agents disabled by default
3. **Gradual Rollout**: Test with single agent before enabling all
4. **Fallback Logic**: If new agent fails, fall back to Claude

## Testing Strategy

### Unit Tests
- Agent interface compliance
- Model configuration loading
- Trigger keyword parsing
- OpenRouter client functionality

### Integration Tests
- Multi-agent PR creation
- Agent fallback chains
- Rate limiting behavior
- Security model enforcement

### End-to-End Tests
- Full issue → PR → review → merge flow
- Multiple agents on same issue
- Configuration switching
- Performance under load

## Success Metrics

1. **Adoption**: Number of users enabling additional agents
2. **Performance**: Response time per agent
3. **Quality**: Code review accuracy across agents
4. **Cost**: Token usage per agent per task
5. **Reliability**: Success rate per agent

## Future Enhancements

1. **Agent Collaboration**: Multiple agents working together on complex tasks
2. **Specialized Models**: Task-specific model selection
3. **Custom Agents**: Plugin system for user-defined agents
4. **Agent Benchmarking**: Automated quality comparisons
5. **Cost Optimization**: Smart routing based on task complexity

## Key Architectural Changes

### Terminal-Based Integration
All three new agents are CLI tools, not API services. This fundamentally changes our integration approach:

1. **Subprocess Management**: Need robust process spawning and communication
2. **Authentication**: Each tool has its own auth mechanism (API keys, config files)
3. **No Containerization**: These tools expect to run on the host with full filesystem access
4. **Interactive Challenges**: Tools designed for human interaction need automation wrappers

### Authentication Models
- **OpenCode**: Requires `opencode auth login` or API key configuration
- **Codex CLI**: Needs OpenAI API key or Plus/Pro account
- **Crush**: Supports multiple providers via environment variables or config files

## Dependencies

### Required Services
- OpenRouter.ai account (for Qwen models)
- OpenAI API key (for Codex CLI)
- GitHub API access
- Host machine installations (no Docker for these agents)
- Python 3.11+ for agent wrapper scripts

### External Tools
- OpenCode: https://github.com/sst/opencode (Terminal UI)
- Codex CLI: https://github.com/openai/codex (New CLI tool)
- Crush: https://github.com/charmbracelet/crush (Charm CLI)

### System Requirements
- Node.js and npm (for OpenCode and Codex CLI)
- Go 1.24+ (for Crush if building from source)
- Modern terminal emulator
- Linux/macOS (Windows via WSL2 for some tools)

### Infrastructure
- Self-hosted GitHub runners
- Agent host machines (with tool binaries installed)
- API key storage (GitHub secrets + local configs)

## Risk Mitigation

1. **API Costs**: Set spending limits on OpenRouter
2. **Security**: Regular security audits of agent code
3. **Performance**: Cache responses where appropriate
4. **Reliability**: Health checks for each agent
5. **Compatibility**: Version pinning for stability

## Timeline

- **Week 1**: Core infrastructure and abstraction layer
- **Week 2**: Individual agent implementations
- **Week 3**: Pipeline integration and testing
- **Week 4**: Documentation and deployment
- **Week 5**: Monitoring and optimization

## CLI Integration Challenges

### 1. Non-Interactive Automation
These tools are designed for interactive use. We need to:
- Create non-interactive wrappers for each tool
- Handle tool prompts and confirmations programmatically
- Manage session state across multiple invocations
- Deal with terminal UI elements that expect human interaction

### 2. Output Parsing
Each tool has different output formats:
- **OpenCode**: Terminal UI with ANSI escape codes
- **Codex CLI**: Structured but interactive output
- **Crush**: Session-based with potential formatting

### 3. Error Handling
- Subprocess crashes and timeouts
- Authentication failures
- Model availability issues
- Network connectivity problems

## Open Questions

1. **CLI Automation**: How to best automate tools designed for interactive use?
2. **Session Management**: Should we maintain long-running agent processes or spawn per-task?
3. **Output Parsing**: Should we request structured output modes from tool maintainers?
4. **Authentication**: How to securely manage multiple API keys and auth methods?
5. **Fallback Strategy**: How to handle when a CLI tool is unavailable or fails?
6. **Performance**: Will subprocess overhead impact response times significantly?
7. **Updates**: How to handle tool updates that might change CLI interfaces?
8. **Debugging**: How to provide visibility into CLI agent operations for troubleshooting?
