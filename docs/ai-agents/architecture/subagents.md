# AI Agent Subagents System

This document describes the subagents system that enhances the AI agent capabilities with specialized personas.

## Overview

The AI agents use specialized personas to handle specific tasks more effectively:

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
│ - IssueMonitor      │
│ - PRMonitor         │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  SubagentManager    │
│ - Load personas     │
│ - Execute tasks     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   AI Agent CLI      │
│ with custom persona │
└─────────────────────┘
```

## Key Components

### 1. Persona Definitions (`docs/subagents/`)

Each persona is defined in a markdown file that provides:
- Role description and responsibilities
- Decision framework
- Implementation guidelines
- Quality standards
- Communication style

Available personas:
- **tech-lead.md**: Technical leadership and feature implementation
- **qa-reviewer.md**: Quality assurance and code review
- **security-auditor.md**: Security analysis and vulnerability detection

### 2. Subagent Manager

The core module that:
- Loads persona definitions
- Builds prompts with context
- Executes AI agents with personas
- Handles error cases

### 3. Integration with Monitors

- **IssueMonitor**: Uses tech-lead persona for feature implementation
- **PRMonitor**: Uses qa-reviewer persona for addressing feedback

## Usage Examples

### In Python Code

```python
from github_ai_agents.subagents import SubagentManager

# Initialize manager
manager = SubagentManager()

# Execute with persona
success, stdout, stderr = manager.execute_with_persona(
    persona="tech-lead",
    task="Implement user authentication feature",
    context={"issue_number": 123, "branch_name": "feature-auth"}
)
```

### With Monitor Integration

The monitors automatically use appropriate personas:

```python
from github_ai_agents.monitors import IssueMonitor

# The monitor will use tech-lead persona automatically
monitor = IssueMonitor()
monitor.process_issues()
```

## Benefits

1. **Specialized Expertise**: Each persona focuses on specific aspects
2. **Consistent Quality**: Personas enforce standards and best practices
3. **Better Context**: AI agents understand the full project context
4. **Flexibility**: Easy to add new personas or modify existing ones
5. **Improved Security**: Security-focused personas for sensitive operations

## Adding New Personas

1. Create a new markdown file in `docs/subagents/` directory
2. Define the persona's role, responsibilities, and guidelines
3. Update the subagent manager to include the new persona
4. Create convenience functions if needed

Example persona structure:
```markdown
# [Persona Name] Persona

## Role
Brief description of the persona's role and purpose.

## Responsibilities
- Key responsibility 1
- Key responsibility 2
- Key responsibility 3

## Decision Framework
Guidelines for making decisions in this role.

## Implementation Guidelines
Specific technical guidelines for this persona.

## Quality Standards
Standards that must be met by this persona.

## Communication Style
How this persona should communicate in comments and PRs.
```

## Security Considerations

- All subagents inherit the security model from the main agents
- Command injection prevention through structured prompts
- Secrets masking in all outputs
- User authorization checks remain in place
- Commit SHA validation still enforced

## Agent-Specific Persona Support

Different AI agents may have varying levels of persona support:

| Agent | Persona Support | Notes |
|-------|----------------|-------|
| Claude | Full | Native persona/role support |
| OpenCode | Full | System prompt configuration |
| Gemini | Full | Role-based prompting |
| Crush | Partial | Limited persona features |

## Future Enhancements

- Additional personas for specific tasks (e.g., performance optimizer, documentation writer)
- Persona composition for complex tasks
- Learning from successful implementations
- Metrics and analytics on persona effectiveness
