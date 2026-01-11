# AI Agents Documentation

This project utilizes multiple AI agents working in harmony to accelerate development, automate issue management, and maintain high code quality.

> **New to the agent system?** Start with the [Board-Centric Workflow Guide](board-workflow.md) for the complete end-to-end flow from issue to merged PR.

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
- Receives `docs/agents/project-context.md` for targeted feedback
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

### 4. Board Agent Worker

**Role**: Automated issue implementation from project board

**Responsibilities**:
- Processes issues from GitHub Projects v2 board
- Claims work to prevent agent conflicts
- Creates pull requests for approved issues
- Updates board status throughout lifecycle

**Location**: `github_agents` package

**Key Features**:
- Board-gated: Issues must be triaged to board first
- Requires `[Approved]` trigger from authorized admin
- Claim management prevents duplicate work
- Creates feature branches automatically
- Creates pull requests linked to issues
- Runs every 12 hours via GitHub Actions (or manual trigger)

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
┌──────────────────────────────────────────────────────────────────┐
│                   Board-Centric Agent Workflow                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌────────────┐  │
│  │   Issue   │──►│  Backlog  │──►│  Add to   │──►│ [Approved] │  │
│  │  Created  │   │  Refine   │   │   Board   │   │  Trigger   │  │
│  │           │   │   (AI)    │   │ (manual)  │   │  (admin)   │  │
│  └───────────┘   └───────────┘   └───────────┘   └────────────┘  │
│                                                        │         │
│                                                        ▼         │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌────────────┐  │
│  │   Merge   │◄──│   Human   │◄──│  AI/Human │◄──│   Agent    │  │
│  │ (manual)  │   │ Approval  │   │ Feedback  │   │ Creates PR │  │
│  └───────────┘   └───────────┘   └───────────┘   └────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

> **Detailed walkthrough**: See [Board-Centric Workflow Guide](board-workflow.md)

### Development Flow

1. **Issue Refinement**:
   - User creates issue
   - AI agents add insights (architecture, security, implementation)
   - Issue accumulates context over time

2. **Triage to Board**:
   - Maintainer reviews issue and insights
   - Adds issue to GitHub Projects v2 board
   - Sets status to "Todo"

3. **Approval**:
   - Authorized admin comments `[Approved][Agent]`
   - Agent selection: explicit > board field > config priority

4. **PR Creation**:
   - Board Agent Worker claims issue
   - Creates feature branch
   - Implements fix
   - Opens PR linked to issue

5. **Review Phase**:
   - Gemini automatically reviews PR
   - PR Review Monitor responds to feedback
   - Human comments addressed

6. **Merge**:
   - All CI checks pass
   - Human approves PR
   - Merge completes, issue auto-closes

### Real-World Example

```bash
# 1. User creates issue: "Add dark mode support"
# 2. Issue Monitor requests more details
# 3. User provides details
# 4. Issue Monitor creates PR automatically

# 5. Gemini reviews PR:
# - "Security: Check user preferences securely"
# - "Style: Use consistent CSS variables"

# 6. PR Review Monitor addresses feedback
# - Implements secure preference storage
# - Updates CSS to use variables
# - Commits: "Address PR review feedback"

# 7. PR Review Monitor comments:
# "Addressed 2 critical issues
#  Fixed 3 inline code comments
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
pip install -e ./packages/github_agents

# Run PR monitor
python -m github_agents.cli pr-monitor

# Board work is typically triggered via GitHub Actions
# but can be tested locally via the workflow_dispatch trigger
```

### GitHub Actions Automation

| Workflow | Purpose | Schedule |
|----------|---------|----------|
| `scheduled-agent-work.yml` | Process board work | Every 12 hours |
| `board-agent-worker.yml` | Reusable agent executor | Called by above |
| `backlog-refinement.yml` | AI insights on issues | Manual |
| `pr-review-monitor.yml` | Respond to PR feedback | Hourly + events |
| `pr-validation.yml` | Gemini PR review | PR events |

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
- Keep `docs/agents/project-context.md` updated
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

1. **Issue Not Being Picked Up**:
   ```bash
   # Check scheduled-agent-work.yml logs
   gh run list --workflow=scheduled-agent-work.yml
   ```
   - Verify issue is on the project board with "Todo" status
   - Check `[Approved]` comment exists from `agent_admin`
   - Look for blocking issues

2. **Agent Not Responding to Feedback**:
   - Check `pr-review-monitor.yml` workflow runs
   - Verify review state is "changes_requested"
   - Check agent availability (Claude auth, API keys)

3. **PR Stuck in Draft**:
   - Check all CI checks pass
   - Verify no "changes_requested" reviews
   - Review agent comments for errors

## Future Enhancements

- Integration with more AI models
- Custom training on project patterns
- Automated testing improvements
- Performance metrics dashboard
- Multi-repository support
- Slack/Discord notifications

---

This comprehensive AI agent system enables a single developer to maintain professional-grade code quality with minimal manual intervention, effectively multiplying productivity through intelligent automation.
