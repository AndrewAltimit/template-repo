# AI Agents Documentation

This project utilizes multiple AI agents working in harmony to accelerate development, automate issue management, and maintain high code quality.

## The AI Agent Ecosystem

### 1. Claude Code (Primary Development Assistant)

**Role**: Main development partner for complex tasks

**Responsibilities**:
- Architecture design and implementation
- Complex refactoring and debugging
- Writing comprehensive documentation
- Creating and modifying CI/CD pipelines
- Test development and coverage improvement
- Following project-specific guidelines in AGENTS.md and CLAUDE.md

**Access**: claude.ai/code

**Key Features**:
- Deep understanding of entire codebase
- Can execute commands and modify multiple files
- Follows container-first philosophy
- Optimized for single-maintainer workflow

### 2. Gemini CLI (Automated PR Reviewer)

**Role**: Quality gatekeeper for all code changes

**Responsibilities**:
- Automatically reviews every pull request
- Focuses on security vulnerabilities
- Checks container configurations
- Validates adherence to project standards
- Provides actionable feedback

**Setup**: Runs on self-hosted runners via Node.js

**Key Features**:
- Conversation history automatically cleared via MCP tool before each review
- Receives PROJECT_CONTEXT.md for targeted feedback
- Non-blocking (PR can proceed if review fails)
- Focuses on project-specific concerns
- Reviews containerization, security, and code quality
- Provides actionable feedback within 3-5 minutes

### 3. GitHub Copilot (Code Review)

**Role**: Additional code review perspective

**Responsibilities**:
- Reviews code changes in pull requests
- Suggests improvements and optimizations
- Identifies potential issues
- Provides alternative implementations

**Access**: GitHub pull request interface

**Key Features**:
- Complements Gemini's automated reviews
- Provides inline suggestions
- Focuses on code quality and best practices

### 4. Issue Monitor Agent (NEW)

**Role**: Automated issue management and PR creation

**Responsibilities**:
- Monitors GitHub issues for completeness
- Requests additional information when needed
- Creates pull requests for actionable issues
- Updates issue status with PR links

**Location**: `github_agents` package

**Key Features**:
- Checks for required fields (description, steps to reproduce, etc.)
- Comments with specific information requests
- Uses Claude Code CLI to implement fixes
- Creates feature branches automatically
- Creates draft pull requests for initial implementations
- Runs every hour via GitHub Actions

### 5. PR Review Monitor Agent (NEW)

**Role**: Automated response to PR review feedback

**Responsibilities**:
- Monitors PR reviews from Gemini and other bots
- Parses review feedback for actionable items
- Implements requested changes automatically
- Comments when changes are complete

**Location**: `github_agents` package

**Key Features**:
- Detects "changes requested" reviews
- Extracts inline code comments
- Uses Claude Code to address feedback
- Commits and pushes fixes
- Automatically undrafts PRs when ready (all checks passing, no review changes needed)
- Monitors pipeline failures and attempts fixes
- Updates PR with completion status

## AI Safety Training

**Important**: Working with advanced AI systems requires understanding potential risks and safety measures. Before deploying AI agents in production, review the [AI Safety Training Guide](human-training.md) which covers:

- Understanding AI deception and hidden behaviors
- Scalable oversight techniques for managing smarter systems
- Capability escalation scenarios and mitigation strategies
- Specification gaming and reward hacking prevention
- Trust and control frameworks
- Emergency procedures for suspected misalignment

This training is based on educational content from AI safety researcher Robert Miles and provides practical knowledge for safe human-AI collaboration.

### sleeper agents Integration

The repository includes an advanced **sleeper agents System** that automatically scans AI models for potential backdoors and hidden behaviors:

- **Automated Testing**: Runs as part of CI/CD pipeline when AI-related code changes
- **Multiple Detection Methods**: Residual stream analysis, attention patterns, and behavioral testing
- **CPU and GPU Support**: Can run on both CPU (for CI) and GPU (for comprehensive analysis)
- **Integration Points**:
  - PR validation automatically triggers sleeper agents tests
  - Issue Monitor and PR Review Monitor agents are scanned for anomalies
  - Custom models can be evaluated using the CLI interface

See the [sleeper agents Package](../../packages/sleeper_agents/README.md) for detailed documentation.

## How They Work Together

### Complete Automation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Repository                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐     ┌──────────────┐    ┌─────────────┐ │
│  │    Issues    │────►│ Issue Monitor│───►│  Create PR  │ │
│  └──────────────┘     └──────────────┘    └─────────────┘ │
│                                                    │        │
│                                                    ▼        │
│  ┌──────────────┐     ┌──────────────┐    ┌─────────────┐ │
│  │ Pull Request │◄────│   PR Review  │◄───│ Gemini Bot  │ │
│  └──────────────┘     │   Monitor    │    └─────────────┘ │
│          │             └──────────────┘                     │
│          │                     │                            │
│          └─────────────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Development Flow

1. **Issue Creation**:
   - User creates issue
   - Issue Monitor checks completeness
   - Requests more info OR creates PR

2. **PR Creation**:
   - Issue Monitor uses Claude Code
   - Creates feature branch
   - Implements fix
   - Opens draft PR for review

3. **Review Phase**:
   - Gemini automatically reviews PR
   - Copilot provides additional suggestions
   - PR Review Monitor detects feedback

4. **Feedback Implementation**:
   - PR Review Monitor parses feedback
   - Uses Claude Code to fix issues
   - Commits and pushes changes
   - Comments on completion

5. **PR Ready for Review**:
   - When all checks pass and no changes needed
   - PR Review Monitor automatically undrafts the PR
   - PR is marked as ready for final review

### Real-World Example

```bash
# 1. User creates issue: "Add dark mode support"
# 2. Issue Monitor requests more details
# 3. User provides details ✨
# 4. Issue Monitor creates PR automatically

# 5. Gemini reviews PR:
# - "Security: Check user preferences securely"
# - "Style: Use consistent CSS variables"

# 6. PR Review Monitor addresses feedback
# - Implements secure preference storage
# - Updates CSS to use variables
# - Commits: "Address PR review feedback"

# 7. PR Review Monitor comments:
# "✅ Addressed 2 critical issues
#  ✅ Fixed 3 inline code comments
#  All tests passing."
```

### Division of Labor

| Task | Claude Code | Gemini CLI | Copilot | OpenCode | Crush | Codex |
|------|------------|------------|---------|----------|--------|-------|
| Architecture Design | Primary | No | No | Secondary | Secondary | Secondary |
| Implementation | Primary | No | No | Secondary | Secondary | Secondary |
| Documentation | Primary | No | No | Secondary | Secondary | Secondary |
| Code Review | Secondary | Primary | Secondary | Secondary | Secondary | Secondary |
| Issue Triage | Secondary | No | No | Secondary | Secondary | Secondary |
| Review Response | Secondary | No | No | Secondary | Secondary | Secondary |

## Configuration

### Agent Configuration

```json
{
  "agents": {
    "issue_monitor": {
      "enabled": true,
      "min_description_length": 50,
      "required_fields": ["description", "expected behavior", "steps to reproduce"],
      "actionable_labels": ["bug", "feature", "enhancement"],
      "check_interval_minutes": 60
    },
    "pr_review_monitor": {
      "enabled": true,
      "review_bot_names": ["gemini-bot", "github-actions[bot]"],
      "auto_fix_threshold": {
        "critical_issues": 0,
        "total_issues": 5
      },
      "check_interval_minutes": 60
    }
  }
}
```

### Running Agents Locally

```bash
# Install the GitHub AI Agents package
pip install -e ./github_agents

# Run specific agents
python -m github_agents.cli issue-monitor
python -m github_agents.cli pr-monitor

# Or use the installed commands directly
issue-monitor
pr-monitor
```

### GitHub Actions Automation

- **issue-monitor.yml**: Runs every hour
- **pr-review-monitor.yml**: Runs every hour and triggered by PR reviews

## Best Practices

### For Issue Creation
- Use issue templates
- Apply appropriate labels (bug, feature, etc.)
- Provide detailed descriptions
- Include code examples when relevant

### For Claude Code
- Provide clear AGENTS.md and CLAUDE.md guidelines
- Use for complex, multi-file changes
- Leverage for documentation and tests
- Ask to follow container-first approach

### For Gemini Reviews
- Keep PROJECT_CONTEXT.md updated
- Clear history before reviews
- Focus feedback on security and standards
- Don't block PR on review failures

### For Agent Monitoring
- Check agent logs regularly
- Monitor for failed runs
- Review agent comments for accuracy
- Manually override when necessary

## Security Considerations

1. **Token Management**: All tokens via environment variables
2. **Limited Permissions**: Repository-scoped access only
3. **Human Review Required**: PRs still need approval
4. **Isolated Execution**: Agents run in containers
5. **Audit Trail**: All actions logged and commented

## Benefits of Multi-Agent Approach

1. **24/7 Automation**: Issues addressed automatically
2. **Consistent Quality**: Multiple review layers
3. **Fast Turnaround**: 15-minute issue response
4. **Reduced Manual Work**: Automatic PR creation
5. **Learning System**: Agents improve over time
6. **Complete Workflow**: Issue to merged PR
7. **Zero Human Intervention**: For routine tasks

## Troubleshooting

### Common Issues

1. **Agent Not Running**:
   ```bash
   # Check GitHub Actions logs
   gh run list --workflow=issue-monitor.yml
   ```

2. **Missing Information Requests**:
   - Verify agent hasn't already commented
   - Check issue has proper labels
   - Review config.json settings

3. **PR Review Not Addressed**:
   - Ensure review is from configured bot
   - Check for "changes requested" state
   - Verify Claude CLI is accessible

## Future Enhancements

- Integration with more AI models
- Custom training on project patterns
- Automated testing improvements
- Performance metrics dashboard
- Multi-repository support
- Slack/Discord notifications

---

This comprehensive AI agent system enables a single developer to maintain professional-grade code quality with minimal manual intervention, effectively multiplying productivity through intelligent automation.
