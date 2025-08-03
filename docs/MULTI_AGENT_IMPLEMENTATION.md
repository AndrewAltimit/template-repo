# Multi-Agent Implementation Guide

This document describes the complete implementation of the multi-agent system, featuring four AI agents: Claude, Gemini, OpenCode, and Crush.

## Overview

The multi-agent system allows you to use different AI coding assistants for various tasks. Each agent has its own strengths and can be selected based on the task at hand.

**Implementation Status**: ✅ Fully Implemented
- All agents have complete implementations with proper error handling
- Hybrid execution model: Host agents (Claude/Gemini) and containerized agents (OpenCode/Crush)
- Automatic detection and switching between local and Docker execution for containerized agents
- Security manager with user authorization and rate limiting
- Two functional monitors: IssueMonitor and PRMonitor
- Both monitors support all agents through trigger keywords

## Architecture

1. **Host Agents** (require specific host configuration):
   - **Claude** (Anthropic) - Requires subscription authentication
   - **Gemini** (Google) - Requires Docker socket access

2. **Containerized Agents** (run in `openrouter-agents` container):
   - **OpenCode** (SST) - Terminal-based coding agent
   - **Crush** (Charm Bracelet) - Flexible multi-provider tool

## Configuration

### Environment Variables

```bash
# Required
GITHUB_TOKEN=your_github_token
GITHUB_REPOSITORY=owner/repo
OPENROUTER_API_KEY=your_openrouter_key

# Optional
ENABLE_AI_AGENTS=true
ANTHROPIC_API_KEY=your_anthropic_key  # For API-based Claude
```

### Agent Configuration (.agents.yaml)

```yaml
enabled_agents:
  - claude      # Host agent
  - gemini      # Host agent
  - opencode    # Containerized
  - crush       # Containerized

agent_priorities:
  issue_creation: [claude, opencode]
  pr_reviews: [gemini]
  code_fixes: [claude, crush]
```

## Usage

### Running Monitors

```bash
# Issue Monitor (creates PRs from issues)
python3 -m github_ai_agents.cli issue-monitor

# PR Monitor (applies fixes from PR reviews)
python3 -m github_ai_agents.cli pr-monitor

# Run containerized agents manually
./scripts/agents/run_containerized_agents.sh opencode "Implement a REST API"
./scripts/agents/run_containerized_agents.sh crush "Explain Docker networking"
```

### Trigger Commands

In GitHub issues and PR comments, use the format `[ACTION][AGENT]`:

- `[Approved][Claude]` - Use Claude for implementation
- `[Approved][Gemini]` - Use Gemini for implementation
- `[Approved][OpenCode]` - Use OpenCode for implementation
- `[Approved][Crush]` - Use Crush for implementation

For PR reviews:
- `[Fix][Claude]` - Fix the issue with Claude
- `[Address][Gemini]` - Address feedback with Gemini
- `[Implement][OpenCode]` - Implement changes with OpenCode

## Agent Capabilities

### Claude
- **Strengths**: Complex implementation, architecture decisions, refactoring
- **Use Cases**: Primary implementation agent, complex fixes
- **Limitations**: Requires host authentication

### Gemini
- **Strengths**: Code review, optimization suggestions, documentation
- **Use Cases**: PR reviews, code quality improvements
- **Limitations**: Requires Docker socket access

### OpenCode
- **Strengths**: Code generation, automatic OpenRouter detection
- **Use Cases**: Straightforward implementations, code snippets
- **Limitations**: Container-only

### Crush
- **Strengths**: Multi-model support, flexible configuration
- **Use Cases**: Various coding tasks, experimentation
- **Limitations**: Container-only, requires OPENAI_API_KEY workaround

## Implementation Details

### Directory Structure

```
github_ai_agents/
├── agents/              # Agent implementations
│   ├── base.py         # Abstract base classes
│   ├── claude.py       # Claude agent
│   ├── gemini.py       # Gemini agent
│   ├── opencode.py     # OpenCode agent
│   └── crush.py        # Crush agent
├── monitors/            # GitHub monitors
│   ├── issue.py        # Issue monitor
│   └── pr.py           # PR monitor
├── security/            # Security components
│   └── manager.py      # Authorization & rate limiting
└── utils/              # Utilities
    └── github.py       # GitHub API helpers
```

### Docker Setup

```
docker/
├── openrouter-agents.Dockerfile  # Container for OpenRouter agents
└── requirements-agents.txt       # Python dependencies

Tools installed in container:
│   ├── opencode (binary from GitHub)
│   └── mods/crush (Go binary)
```

### Security Model

1. **User Authorization**: Only users in allow list can trigger agents
2. **Rate Limiting**: Configurable per-agent rate limits
3. **Command Validation**: Specific trigger format required
4. **Repository Validation**: Only works on authorized repos

## Testing

```bash
# Run all tests
python -m pytest tests/

# Test specific components
python -m pytest tests/test_agents.py          # Agent tests
python -m pytest tests/test_issue_monitor.py   # Issue monitor tests
python -m pytest tests/test_pr_monitor.py      # PR monitor tests
python -m pytest tests/test_security.py        # Security tests
```

## Current Limitations

1. **Host vs Container**: Claude and Gemini can't run in containers due to authentication requirements
2. **Automated Workflows**: Container agents require manual intervention in GitHub Actions
3. **OpenRouter Dependency**: Container agents rely on OpenRouter API availability

## Future Enhancements

1. **Hybrid Bridge**: Service to proxy between host and container agents
2. **More Agents**: Add support for additional AI providers
3. **Enhanced Security**: More granular permissions and audit logging
4. **Performance**: Caching and parallel agent execution

## References

- [Claude CLI Documentation](https://github.com/anthropics/claude-cli)
- [Gemini CLI Documentation](https://github.com/google/generative-ai-docs)
- [OpenCode Documentation](https://opencode.ai/docs/)
- [mods/Crush Documentation](https://github.com/charmbracelet/mods)
