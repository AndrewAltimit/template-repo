# Migration Guide

This guide helps you migrate from the old scripts-based agent system to the new `github_ai_agents` package.

## What's Changed

### Old Structure
```
scripts/agents/
├── issue_monitor.py
├── issue_monitor_multi_agent.py
├── multi_agent_subagent_manager.py
├── implementations/
│   ├── opencode_agent.py
│   ├── claude_agent.py
│   └── ...
└── security.py
```

### New Structure
```
github_ai_agents/
├── pyproject.toml
├── src/github_ai_agents/
│   ├── agents/
│   ├── monitors/
│   ├── security/
│   └── utils/
└── tests/
```

## Migration Steps

### 1. Install the New Package

```bash
# For development
cd github_ai_agents
pip install -e ".[dev]"

# For production
pip install ./github_ai_agents
```

### 2. Update Imports

Old:
```python
from issue_monitor import IssueMonitor
from multi_agent_subagent_manager import implement_issue_with_agent
from security import SecurityManager
```

New:
```python
from github_ai_agents.monitors import IssueMonitor
from github_ai_agents.agents import OpenCodeAgent, ClaudeAgent
from github_ai_agents.security import SecurityManager
```

### 3. Update Command Line Usage

Old:
```bash
python scripts/agents/issue_monitor.py
python -m scripts.agents.issue_monitor_multi_agent
```

New:
```bash
# Using the CLI
github-ai-agents issue-monitor
issue-monitor  # Direct command

# Or as a module
python -m github_ai_agents.cli issue-monitor
```

### 4. Update GitHub Actions

Change your workflow from:
```yaml
python3 scripts/agents/issue_monitor_multi_agent.py
```

To:
```yaml
pip3 install -e ./github_ai_agents
python3 -m github_ai_agents.cli issue-monitor
```

### 5. Environment Variables

No changes needed - the same environment variables work:
- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY`
- `OPENROUTER_API_KEY`
- `ANTHROPIC_API_KEY`

## Benefits of the New Structure

1. **Clean Imports**: No more relative import issues
2. **Proper Packaging**: Can be installed and distributed
3. **Better Testing**: Isolated test suite with pytest
4. **Extensibility**: Easy to add new agents or monitors
5. **Type Safety**: Full type hints throughout
6. **Documentation**: Integrated documentation

## Backward Compatibility

The old scripts remain in place during transition for backward compatibility and documentation purposes. They serve as a reference for the security model and legacy integration patterns.

## Troubleshooting

### Import Errors
If you get import errors, ensure:
1. The package is installed: `pip list | grep github-ai-agents`
2. You're in the right environment
3. PYTHONPATH includes the project root

### Missing Dependencies
Install all dependencies:
```bash
pip install -e "./github_ai_agents[dev]"
```

### Agent Not Found
Check that agents are available:
```python
from github_ai_agents.agents import OpenCodeAgent
agent = OpenCodeAgent()
print(agent.is_available())
```
