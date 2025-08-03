# GitHub AI Agents

A Python package for AI-powered GitHub automation using multiple AI agents (Claude, OpenCode, Gemini, Crush).

## Features

- **Multi-Agent Support**: Choose from multiple AI agents based on your needs
- **Issue Monitoring**: Automatically respond to GitHub issues with AI-generated implementations
- **PR Review Monitoring**: Process review feedback and generate fixes using multiple AI agents
- **Security**: Built-in security features including user authorization and rate limiting
- **Containerization**: Support for running agents in Docker containers
- **Extensible**: Easy to add new AI agents or monitors

## Installation

### For Development

```bash
# Clone the repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo/packages/github_ai_agents

# Install in development mode with all dependencies
pip install -e ".[dev]"
```

### For Production

```bash
# Install from the repository
pip install git+https://github.com/AndrewAltimit/template-repo.git#subdirectory=packages/github_ai_agents
```

## Quick Start

### Running Issue Monitor

```python
from github_ai_agents.monitors import IssueMonitor

# Initialize the monitor
monitor = IssueMonitor()

# Process issues once
monitor.process_issues()

# Or run continuously
monitor.run_continuous(interval=300)  # Check every 5 minutes
```

### Running PR Review Monitor

```python
from github_ai_agents.monitors import PRMonitor

# Initialize the monitor
monitor = PRMonitor()

# Process PRs once
monitor.process_prs()

# Or run continuously
monitor.run_continuous(interval=300)  # Check every 5 minutes
```

### Using AI Agents Directly

```python
from github_ai_agents.agents import OpenCodeAgent, ClaudeAgent

# Initialize an agent
agent = OpenCodeAgent()

# Check if agent is available
if agent.is_available():
    # Generate code
    response = await agent.generate_code(
        prompt="Create a Python function to calculate fibonacci numbers",
        context={"language": "python"}
    )
    print(response)
```

## Configuration

Create a `.env` file in your project root:

```bash
# GitHub Configuration
GITHUB_TOKEN=your_github_token
GITHUB_REPOSITORY=owner/repo

# AI Agent API Keys
OPENROUTER_API_KEY=your_openrouter_key
ANTHROPIC_API_KEY=your_anthropic_key  # Optional, for API-based Claude

# Security Configuration
ENABLE_AI_AGENTS=true
```

## Available Agents

| Agent | Description | Authentication | Container Support |
|-------|-------------|----------------|-------------------|
| Claude | Anthropic's Claude AI | Subscription/API | Host only |
| OpenCode | Open-source coding AI | API Key | Yes |
| Gemini | Google's Gemini AI | CLI Auth | Host only |
| Crush | Charm Bracelet Mods | API Key | Yes |

## Testing

### Running Tests

```bash
# Run all tests with coverage
./run_tests.sh

# Or manually with pytest
python -m pytest tests/ -v --cov=github_ai_agents

# Run specific test categories
python -m pytest tests/ -m unit      # Unit tests only
python -m pytest tests/ -m integration # Integration tests only
```

### Test Structure

- `tests/test_agents.py` - Unit tests for individual AI agents
- `tests/test_issue_monitor.py` - Tests for issue monitoring functionality
- `tests/test_pr_monitor.py` - Tests for PR review monitoring functionality
- `tests/test_monitors.py` - General monitor tests
- `tests/test_security.py` - Security manager tests
- `tests/test_subagents.py` - Subagent system tests

## Security

The package includes comprehensive security features:

- **User Authorization**: Only pre-approved users can trigger agents
- **Keyword Triggers**: Specific format required (e.g., `[Approved][OpenCode]`)
- **Rate Limiting**: Prevents abuse of AI resources
- **Repository Validation**: Ensures agents only work on authorized repos

See [Security Documentation](docs/security.md) for details.

## Architecture

```
github_ai_agents/
├── agents/          # AI agent implementations
├── monitors/        # GitHub event monitors
├── security/        # Security and authorization
└── utils/           # Utility functions
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details.

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Usage Guide](docs/usage.md)
- [Security Documentation](docs/security.md)
- [API Reference](docs/api.md)

## Implementation Status

Both monitors are fully functional with automated code modification capabilities:

- **Issue Monitor**: Creates PRs with AI-generated implementations (see [Issue Monitor Status](../../docs/ISSUE_MONITOR_IMPLEMENTATION_STATUS.md))
- **PR Monitor**: Applies fixes directly to PR branches (see [PR Monitor Status](../../docs/PR_MONITOR_IMPLEMENTATION_STATUS.md))

The security model ensures only authorized users can trigger code changes through explicit commands.
