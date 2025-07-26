# Claude Code Subagents System

This document describes the new Claude Code subagents system that enhances the AI agent capabilities with specialized personas.

## Overview

The AI agents now use Claude Code with different personas to handle specific tasks more effectively:

- **Tech Lead** persona for implementing features from issues
- **QA Reviewer** persona for addressing PR review feedback
- **Security Auditor** persona for security-focused analysis

## Architecture

```
┌─────────────────────┐
│   GitHub Actions    │
│   (Workflows)       │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Agent Monitors    │
│ - issue_monitor.py  │
│ - pr_review_monitor │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  SubagentManager    │
│ - Load personas     │
│ - Execute tasks     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Claude Code CLI   │
│ with custom persona │
└─────────────────────┘
```

## Key Components

### 1. Persona Definitions (`subagents/`)

Each persona is defined in a markdown file that provides:
- Role description and responsibilities
- Decision framework
- Implementation guidelines
- Quality standards
- Communication style

### 2. Subagent Manager (`subagent_manager.py`)

The core module that:
- Loads persona definitions
- Builds prompts with context
- Executes Claude Code with personas
- Handles error cases

### 3. Updated Monitors

- **issue_monitor.py**: Uses tech-lead persona for feature implementation
- **pr_review_monitor.py**: Uses qa-reviewer persona for addressing feedback

### 4. CLI Integration (`claude_subagent.py`)

Command-line tool for direct subagent usage:
```bash
python claude_subagent.py <persona> <command> [options]
```

## Usage Examples

### In Python Code

```python
from subagent_manager import SubagentManager, implement_issue_with_tech_lead

# Using convenience function
success, output = implement_issue_with_tech_lead(issue_data, branch_name)

# Using SubagentManager directly
manager = SubagentManager()
success, stdout, stderr = manager.execute_with_persona(
    "tech-lead",
    "Implement user authentication feature",
    {"issue_number": 123, "branch_name": "feature-auth"}
)
```

### From Command Line

```bash
# Implement an issue
python claude_subagent.py tech-lead implement --issue 123 --repo owner/repo

# Review a PR
python claude_subagent.py qa-reviewer review --pr 456 --repo owner/repo

# Custom task
python claude_subagent.py security-auditor custom --task "Audit authentication module"
```

## Benefits

1. **Specialized Expertise**: Each persona focuses on specific aspects
2. **Consistent Quality**: Personas enforce standards and best practices
3. **Better Context**: Claude Code understands the full project context
4. **Flexibility**: Easy to add new personas or modify existing ones
5. **Improved Security**: Security-focused personas for sensitive operations

## Adding New Personas

1. Create a new markdown file in `subagents/` directory
2. Define the persona's role, responsibilities, and guidelines
3. Update `claude_subagent.py` to include the new persona in choices
4. Create convenience functions in `subagent_manager.py` if needed

## Security Considerations

- All subagents inherit the security model from the main agents
- Command injection prevention through structured prompts
- Secrets masking in all outputs
- User authorization checks remain in place
- Commit SHA validation still enforced

## Migration from Old System

The previous shell script-based system (`templates/*.sh`) has been replaced. To migrate:

1. Update agent code to use `SubagentManager`
2. Replace shell script calls with persona executions
3. Use the provided wrapper scripts for backward compatibility

## Future Enhancements

- Additional personas for specific tasks (e.g., performance optimizer, documentation writer)
- Persona composition for complex tasks
- Learning from successful implementations
- Metrics and analytics on persona effectiveness
