# GitHub AI Agents Examples

This directory contains example scripts demonstrating different ways to use the GitHub AI Agents framework for automated issue handling, PR reviews, and board integration.

## Overview

The framework enables AI agents to:
- **Monitor Issues**: Automatically implement solutions when triggered
- **Review PRs**: Respond to review feedback and implement fixes
- **Manage Work**: Use GitHub Projects v2 as an external memory system
- **Coordinate**: Multiple agents working without conflicts

All examples follow security-first principles with user authorization and commit validation.

## Examples

### 1. Basic Usage (`basic_usage.py`)

**Purpose**: Simplest way to get started with the framework.

**Usage**:
```bash
# Set environment variables
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo

# Run example
python examples/basic_usage.py
```

**What it shows**:
- Importing core modules
- Initializing monitors with configuration
- Running basic issue and PR checks
- Security validation

**Best for**: Quick experiments, learning the API, understanding core concepts

---

### 2. Issue Monitor (`issue_monitor_example.py`)

**Purpose**: Complete issue monitoring workflow with agent selection.

**Prerequisites**:
- GitHub repository access
- Issue with trigger comment (e.g., `[Approved][OpenCode]`)
- OpenRouter API key for AI agents

**Usage**:
```bash
# Set required environment variables
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo
export OPENROUTER_API_KEY=your_key

# Run monitor
python examples/issue_monitor_example.py
```

**What it shows**:
- Setting up IssueMonitor
- Security configuration with allowed users
- Agent selection (Claude, OpenCode, Gemini, Crush, Codex)
- Detecting triggers in comments
- Generating implementation with AI
- Creating pull requests
- Error handling

**Best for**: Automated issue resolution, understanding agent workflows

---

### 3. PR Monitor (`pr_monitor_example.py`)

**Purpose**: Monitor PRs for review feedback and implement fixes.

**Prerequisites**:
- Open pull request
- Review comment with trigger (e.g., `[Fix][OpenCode]`)
- OpenRouter API key

**Usage**:
```bash
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo
export OPENROUTER_API_KEY=your_key

python examples/pr_monitor_example.py
```

**What it shows**:
- Setting up PRMonitor
- Detecting review comments with triggers
- Implementing fixes based on feedback
- Pushing commits to PR branch
- Handling multiple review comments

**Best for**: Automated PR fixes, tight feedback loops during development

---

### 4. Board Integration (`board_integration_example.py`)

**Purpose**: Using GitHub Projects v2 for work management and coordination.

**Prerequisites**:
- GitHub repository with Projects v2 enabled
- Project with custom fields configured
- Board configuration file (`ai-agents-board.yml`)

**Usage**:
```bash
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo
export GITHUB_PROJECT_NUMBER=1

python examples/board_integration_example.py
```

**What it shows**:
- Initializing BoardManager
- Querying ready work (unblocked, unclaimed issues)
- Claiming work with session tracking
- Updating issue status
- Adding dependencies (blockers)
- Releasing work with completion reason
- Getting dependency graphs

**Best for**: Multi-session workflows, agent memory across restarts, work coordination

---

### 5. Multi-Agent Coordination (`multi_agent_example.py`)

**Purpose**: Demonstrates multiple agents working concurrently without conflicts.

**Prerequisites**:
- GitHub Projects v2 board configured
- Multiple issues ready to work on

**Usage**:
```bash
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo
export GITHUB_PROJECT_NUMBER=1
export OPENROUTER_API_KEY=your_key

python examples/multi_agent_example.py
```

**What it shows**:
- Creating multiple agent instances
- Agent-specific work queries
- Claim-based conflict prevention
- Concurrent execution with asyncio
- Work distribution across agents
- Claim expiration and renewal

**Best for**: Understanding coordination, scaling to multiple agents

---

### 6. Custom Agent (`custom_agent_example.py`)

**Purpose**: Creating custom agents with specific behaviors.

**Usage**:
```bash
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo
export OPENROUTER_API_KEY=your_key

python examples/custom_agent_example.py
```

**What it shows**:
- Extending base agent classes
- Custom trigger patterns
- Specialized implementation logic
- Custom prompt engineering
- Integration with existing monitors

**Best for**: Building specialized agents, custom workflows

---

### 7. GitHub Actions Integration (`github_actions_example.yml`)

**Purpose**: Template for running agents in GitHub Actions workflows.

**Usage**:
```bash
# Copy to your repository
cp examples/github_actions_example.yml .github/workflows/ai-agents.yml

# Configure secrets in GitHub repository settings:
# - GITHUB_TOKEN (automatically provided)
# - OPENROUTER_API_KEY
```

**What it shows**:
- Scheduled agent execution
- Manual workflow dispatch
- Environment variable configuration
- Self-hosted runner usage
- Containerized agent execution

**Best for**: Automated continuous monitoring, production deployment

---

### 8. Security Configuration (`security_example.py`)

**Purpose**: Demonstrates security features and best practices.

**Usage**:
```bash
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo

python examples/security_example.py
```

**What it shows**:
- User authorization with allow lists
- Commit validation to prevent code injection
- Trigger pattern validation
- API key management
- Rate limiting configuration
- Security audit logging

**Best for**: Understanding security model, production hardening

---

## Quick Start Patterns

### Pattern 1: Manual Single-Issue Monitoring

```python
import asyncio
from github_ai_agents.monitors.issue_monitor import IssueMonitor

async def main():
    monitor = IssueMonitor(
        repo="owner/repo",
        github_token="your_token",
        allowed_users=["admin"],
        openrouter_api_key="your_key"
    )
    await monitor.process_issue(123)  # Process specific issue

asyncio.run(main())
```

### Pattern 2: Continuous Monitoring

```python
import asyncio
from github_ai_agents.monitors.issue_monitor import IssueMonitor

async def main():
    monitor = IssueMonitor(
        repo="owner/repo",
        github_token="your_token",
        allowed_users=["admin"],
        openrouter_api_key="your_key"
    )

    while True:
        await monitor.process_recent_issues()
        await asyncio.sleep(300)  # Check every 5 minutes

asyncio.run(main())
```

### Pattern 3: Board-Integrated Workflow

```python
import asyncio
from github_ai_agents.board.config import BoardConfig
from github_ai_agents.board.manager import BoardManager
from github_ai_agents.monitors.issue_monitor import IssueMonitor

async def main():
    # Initialize board
    config = BoardConfig.from_file("ai-agents-board.yml")
    board = BoardManager(config=config, github_token="your_token")
    await board.initialize()

    # Get ready work
    issues = await board.get_ready_work(agent_name="claude", limit=5)

    # Process each issue
    monitor = IssueMonitor(
        repo="owner/repo",
        github_token="your_token",
        board_manager=board  # Pass board manager
    )

    for issue in issues:
        # Claim work
        await board.claim_work(issue.number, "claude", "session-123")

        # Process issue
        await monitor.process_issue(issue.number)

        # Release work
        await board.release_work(issue.number, "claude", "completed")

asyncio.run(main())
```

### Pattern 4: Error Handling and Retry

```python
import asyncio
from github_ai_agents.monitors.issue_monitor import IssueMonitor

async def main():
    monitor = IssueMonitor(
        repo="owner/repo",
        github_token="your_token"
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            await monitor.process_issue(123)
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
            else:
                raise

asyncio.run(main())
```

## Environment Variables

The framework uses these environment variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITHUB_TOKEN` | GitHub API token with repo access | None | Yes |
| `GITHUB_REPOSITORY` | Repository name (owner/repo format) | None | Yes |
| `GITHUB_PROJECT_NUMBER` | GitHub Projects v2 board number | None | For board features |
| `OPENROUTER_API_KEY` | OpenRouter API key for AI agents | None | For AI generation |
| `ENABLE_AI_AGENTS` | Enable/disable agent execution | `true` | No |
| `ALLOWED_USERS` | Comma-separated list of authorized users | None | Recommended |
| `AGENT_TIMEOUT` | Maximum agent execution time (seconds) | `600` | No |
| `MAX_RETRIES` | Maximum retry attempts for failed operations | `3` | No |

### Security Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REQUIRE_AUTHORIZATION` | Require user to be in allowed list | `true` |
| `VALIDATE_COMMITS` | Validate commits haven't changed after approval | `true` |
| `REQUIRE_SIGNATURE` | Require GPG signatures on commits | `false` |

### Board Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `BOARD_CLAIM_TIMEOUT` | Claim expiration time (seconds) | `86400` (24h) |
| `BOARD_RENEWAL_INTERVAL` | Claim renewal interval (seconds) | `3600` (1h) |
| `BOARD_CONFIG_PATH` | Path to board config file | `ai-agents-board.yml` |

## CLI Tools

The package provides command-line tools for direct usage:

### Issue Monitor CLI

```bash
# Run once
issue-monitor

# Continuous monitoring (every 5 minutes)
issue-monitor --continuous --interval 300

# Process specific issue
issue-monitor --target-issue 123

# Review-only mode (no PR creation)
issue-monitor --review-only
```

### PR Monitor CLI

```bash
# Monitor all PRs
pr-monitor

# Monitor specific PR
pr-monitor --pr-number 45

# Continuous monitoring
pr-monitor --continuous
```

### Board CLI

```bash
# Query ready work
board-cli ready --agent claude --limit 5

# Create issue with metadata
board-cli create "Fix bug" --type bug --priority high

# Claim issue
board-cli claim 123 --agent claude

# Update status
board-cli status 123 in-progress

# View dependency graph
board-cli graph 123

# Release work
board-cli release 123 --agent claude --reason completed
```

See [CLI_REFERENCE.md](../docs/CLI_REFERENCE.md) for complete documentation.

## Common Use Cases

### Development: Testing Agent Behavior

```python
# Use review-only mode to see what agents would do
monitor = IssueMonitor(
    repo="owner/repo",
    github_token="token",
    review_only=True  # No PR creation
)
await monitor.process_issue(123)
```

### Production: Continuous Monitoring

```bash
# Run in GitHub Actions on schedule
# See examples/github_actions_example.yml
```

### Research: Multi-Agent Experiments

```python
# Create multiple agents with different prompts/models
agents = [
    create_agent("conservative", temperature=0.2),
    create_agent("creative", temperature=0.8),
    create_agent("balanced", temperature=0.5)
]

# Compare implementations
for agent in agents:
    result = await agent.implement(issue)
    evaluate(result)
```

### Operations: Work Queue Management

```bash
# Get high-priority unblocked work
board-cli ready --priority high --limit 10 --json | \
  jq -r '.[] | .number' | \
  xargs -I {} board-cli claim {} --agent claude
```

## Docker Usage

The agents can run in containers for consistency and zero host dependencies:

```bash
# Using python-ci container (recommended - works regardless of image build state)
docker-compose run --rm python-ci bash -c "pip install -e packages/github_ai_agents && issue-monitor"

# With environment variables
docker-compose run --rm \
  -e GITHUB_TOKEN \
  -e GITHUB_REPOSITORY \
  -e OPENROUTER_API_KEY \
  python-ci bash -c "pip install -e packages/github_ai_agents && pr-monitor"

# Using environment file
docker-compose run --rm --env-file .env python-ci bash -c "\
  pip install -e packages/github_ai_agents && issue-monitor"
```

## Testing Examples

All examples include test mode:

```bash
# Run in test mode (uses mocks, no API calls)
python examples/basic_usage.py --test-mode

# Validate configuration without execution
python examples/issue_monitor_example.py --validate-only

# Dry-run mode (shows what would happen)
python examples/board_integration_example.py --dry-run
```

## Troubleshooting

### "No module named 'github_ai_agents'"

```bash
# Install package in editable mode
pip install -e packages/github_ai_agents
```

### "GitHub API rate limit exceeded"

```bash
# Use authenticated token (higher rate limits)
export GITHUB_TOKEN=your_token

# Or wait for rate limit reset
# Check remaining: curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
```

### "Board not found"

```bash
# Verify project number in URL
# GitHub URL: github.com/users/owner/projects/1
export GITHUB_PROJECT_NUMBER=1

# Verify token has 'project' scope
# Regenerate token with correct scopes if needed
```

### "Agent execution timeout"

```bash
# Increase timeout for long-running tasks
export AGENT_TIMEOUT=1200  # 20 minutes

# Or split into smaller issues
```

## Next Steps

1. **Start Simple**: Run `basic_usage.py` to understand core concepts
2. **Try Monitoring**: Run `issue_monitor_example.py` with a test issue
3. **Enable Board**: Set up GitHub Projects v2 and try `board_integration_example.py`
4. **Scale Up**: Try `multi_agent_example.py` for concurrent agents
5. **Customize**: Create your own agent with `custom_agent_example.py` as a template
6. **Deploy**: Use `github_actions_example.yml` for automated monitoring

## Documentation

### Main Documentation
- [Package README](../README.md) - Overview and installation
- [Security Model](../docs/security.md) - Security architecture
- [Board Integration](../docs/board-integration.md) - GitHub Projects v2 guide

### Reference Documentation
- [API Reference](../docs/API_REFERENCE.md) - Python API documentation
- [CLI Reference](../docs/CLI_REFERENCE.md) - Command-line tools
- [Architecture](../docs/architecture.md) - System design

## Contributing

When creating new examples:

1. **Follow the pattern**: Use the same structure as existing examples
2. **Add docstrings**: Explain what the example demonstrates
3. **Update README**: Add entry in the Examples section above
4. **Test thoroughly**: Ensure example works with fresh install
5. **Keep it simple**: Examples should be educational, not production code

## Questions?

- Review the [main documentation](../README.md)
- Check [security model](../docs/security.md) for authorization details
- See [board integration](../docs/board-integration.md) for Projects v2 setup
- Open an issue for bugs or feature requests
