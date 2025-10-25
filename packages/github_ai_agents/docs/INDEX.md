# GitHub AI Agents Documentation

Welcome to the GitHub AI Agents documentation. This package provides automated code generation and review capabilities through AI agents integrated with GitHub Issues and Pull Requests.

## Getting Started

- [README](../README.md) - Project overview and features
- [Quick Start Guide](QUICK_START.md) - Get running in 5 minutes
- [Installation Guide](INSTALLATION.md) - Detailed installation and setup
- [CLI Reference](CLI_REFERENCE.md) - Command-line interface reference

## Core Concepts

### Architecture
- [Architecture Overview](architecture.md) - System design and components
- [Security Model](security.md) - Security and authorization system
- [Autonomous Mode](autonomous_mode.md) - Autonomous agent operation

### Agents
- [Subagents](subagents.md) - Specialized agent types and capabilities
- Available Agents:
  - **Claude** - Primary development assistant via Claude CLI
  - **OpenCode** - Comprehensive code generation via OpenRouter
  - **Gemini** - Code review and analysis
  - **Crush** - Fast code generation and conversion
  - **Codex** - AI-powered code completion *(optional)*

## User Guides

### Monitors

#### Issue Monitor
Automatically processes GitHub issues with trigger keywords to create pull requests.

**Features:**
- Multi-agent support (Claude, OpenCode, Gemini, Crush)
- Security-based authorization with allow list
- Automated PR creation with generated code
- Rate limiting and validation

**Usage:**
```bash
issue-monitor --continuous
```

See [Issue Monitor Tests](../tests/integration/test_issue_monitor.py) for examples.

#### PR Monitor
Monitors pull requests for review comments and implements requested changes.

**Features:**
- Automated fix implementation from review feedback
- Multi-agent code generation
- Commit and push automation
- Integration with existing PRs

**Usage:**
```bash
pr-monitor --pr-number 123
```

See [PR Monitor Tests](../tests/integration/test_pr_monitor.py) for examples.

### Security

The package implements a comprehensive security model:
- **User Authorization:** Allow list of approved GitHub users
- **Keyword Triggers:** `[Approved][AgentName]` format required
- **Rate Limiting:** Prevents abuse and API quota exhaustion
- **Repository Validation:** Ensures agents only act on authorized repos
- **Commit Validation:** Prevents code injection after approval

See [Security Documentation](security.md) for complete details.

## Advanced Topics

### Integrations

#### TTS Integration
Text-to-speech capabilities for PR reviews and broadcasts.

**Features:**
- Multiple voice profiles (professional, casual, technical)
- ElevenLabs integration
- Automated review narration
- Voice catalog management

See [TTS Integration Guide](tts-integration.md) for details.

#### Subagent System
Specialized agents for specific tasks:
- **Tech Lead** - Architecture and design review
- **Security Auditor** - Security vulnerability detection
- **QA Reviewer** - Test coverage and quality analysis

See [Subagent Documentation](subagents.md) for complete details.

#### Board Integration
GitHub Projects v2 integration for agent coordination and work tracking.

**Features:**
- Work queue management with ready work detection
- Timestamp-based claim system (24-hour timeout, 1-hour renewal)
- Dependency tracking (blocks, parent-child, discovered from)
- Multi-agent coordination without conflicts
- GraphQL API integration with GitHub Projects v2
- MCP server with 11 core tools
- Docker containerization with health checks

See [Board Integration Guide](board-integration.md) for complete documentation.

### GitHub Actions

The package integrates with GitHub Actions for automated workflows:

**Available Workflows:**
- Issue monitoring (hourly schedule)
- PR review monitoring (hourly schedule)
- Automated testing and validation

**Example Configuration:**
```yaml
name: AI Agent Issue Monitor

on:
  schedule:
    - cron: '0 * * * *'  # Every hour
  workflow_dispatch:

jobs:
  monitor:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - name: Run Issue Monitor
        run: issue-monitor
```

## API Reference

### Python API
Complete Python API documentation for programmatic usage.

See [API Reference](API_REFERENCE.md) for complete details.

### CLI Commands
Comprehensive command-line interface reference.

See [CLI Reference](CLI_REFERENCE.md) for all available commands.

## Development

### Testing

The package includes a comprehensive test suite:
- **Unit Tests:** Fast, isolated component tests (>90% coverage target)
- **Integration Tests:** Workflow and interaction tests (>80% coverage target)
- **E2E Tests:** Full end-to-end workflow tests
- **TTS Tests:** Text-to-speech integration tests

See [Testing Guide](../tests/README.md) for complete details.

### Contributing

Development workflow:
```bash
# Install package in development mode
pip install -e packages/github_ai_agents

# Run tests
pytest tests/ -v --cov=github_ai_agents

# Run linting
./automation/ci-cd/run-ci.sh lint-basic

# Format code
./automation/ci-cd/run-ci.sh autoformat
```

### Version History

- [CHANGELOG](../CHANGELOG.md) - Version history and release notes

## Examples

Comprehensive usage examples:
- Basic usage patterns
- Issue monitoring workflows
- PR review automation
- Board integration patterns
- Multi-agent coordination
- Custom agent development
- Security features
- GitHub Actions templates

See [Examples Directory](../examples/) for complete examples and usage patterns.

## Troubleshooting

### Common Issues

#### Agent Not Available
**Problem:** Agent shows as unavailable
**Solution:** Check API keys and CLI installation:
```bash
# For Claude
which claude-code  # Should return path

# For OpenCode/Crush
echo $OPENROUTER_API_KEY  # Should be set
```

#### Permission Denied
**Problem:** Agent cannot create PR
**Solution:** Check GitHub token permissions:
```bash
# Token needs repo scope
gh auth status
```

#### Rate Limiting
**Problem:** GitHub API rate limit exceeded
**Solution:** Reduce monitoring frequency or use GitHub Actions token

For more troubleshooting help, see test files in `tests/` directory for working examples.

## Support

- **Issues:** [GitHub Issues](https://github.com/AndrewAltimit/template-repo/issues)
- **Discussions:** [GitHub Discussions](https://github.com/AndrewAltimit/template-repo/discussions)
- **Documentation:** This index and linked guides

## Additional Information

- **Python Support:** 3.11+
- **License:** See LICENSE file in repository root
- **Version History:** See [CHANGELOG](../CHANGELOG.md)
