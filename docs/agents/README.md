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

### 2. Automated PR Reviewers (Claude + OpenRouter)

**Role**: Quality gate for all code changes

`.github/workflows/pr-validation.yml` runs three reviews in parallel on every non-draft PR:
- **Claude security review** (`security` profile in `review-profiles.yaml`)
- **Claude quality review** (`quality` profile)
- **OpenRouter general review** (`openrouter-general` profile, `qwen/qwen3.7-max`)

An optional AgentCore review runs when the `agentcore-review` label is applied. Reviews are non-blocking. The review prompt includes excerpts of `README.md`, `CONTRIBUTING.md`, and `CLAUDE.md` (read from the base branch so a PR cannot rewrite reviewer guidance).

### 3. GitHub Copilot (Code Review)

**Role**: Additional code review perspective

**Responsibilities**:
- Reviews code changes in pull requests
- Suggests improvements and optimizations
- Identifies potential issues
- Provides alternative implementations

**Access**: GitHub pull request interface

**Key Features**:
- Complements the Claude and OpenRouter automated reviews
- Provides inline suggestions
- Focuses on code quality and best practices

### 4. Board Agent Worker

**Role**: Automated issue implementation from project board

**Responsibilities**:
- Processes issues from GitHub Projects v2 board
- Claims work to prevent agent conflicts
- Creates pull requests for approved issues
- Updates board status throughout lifecycle

**Location**: `tools/rust/github-agents-cli/` (Rust CLI)

**Key Features**:
- Board-gated: Issues must be triaged to board first
- Requires `[Approved]` trigger from authorized admin
- Claim management prevents duplicate work
- Creates feature branches automatically
- Creates pull requests linked to issues
- Runs every 12 hours via GitHub Actions (or manual trigger)

### 5. PR Review Monitor Agent

**Role**: Automated response to PR review feedback

**Responsibilities**:
- Monitors PR reviews from Claude, OpenRouter, and other bots
- Parses review feedback for actionable items
- Implements requested changes automatically
- Comments when changes are complete

**Location**: `tools/rust/github-agents-cli/` (Rust CLI)

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
- **Rust Orchestration CLI**: The `sleeper-cli` binary provides fast host-side orchestration without requiring Python locally; it manages Docker containers, submits jobs, and generates reports
- **Integration Points**:
  - PR validation automatically triggers sleeper agents tests (Python ML + Rust CLI)
  - Issue Monitor and PR Review Monitor agents are scanned for anomalies
  - Custom models can be evaluated using either the Python or Rust CLI

See the [sleeper agents Package](../../packages/sleeper_agents/README.md) for detailed documentation.

### Economic Agents Integration

The repository includes an **Economic Agents Simulation Framework** that demonstrates autonomous AI economic capability for governance research:

- **Autonomous Operation**: Agents complete tasks, earn cryptocurrency, form companies, and seek investment without human intervention
- **Mock-to-Real Architecture**: Identical REST API interfaces allow switching between simulation and production backends
- **Governance Research**: Raises questions about AI legal personhood, fiduciary duty, liability, and competitive dynamics
- **Simulation Realism**: Latency, competition, market cycles, reputation systems, and investor behavior modeling
- **Integration Points**:
  - Uses Claude Code as the execution engine for task completion
  - Sub-agent hierarchy (board members, executives, ICs) for organizational simulation
  - Decision engine with LLM-powered strategic resource allocation
  - Dashboard for real-time observation of agent economic behavior

See the [Economic Agents Package](../../packages/economic_agents/README.md) for detailed documentation.

### OASIS_OS (External Repository)

**OASIS_OS** has been moved to its own dedicated repository: [github.com/AndrewAltimit/oasis-os](https://github.com/AndrewAltimit/oasis-os)

An embeddable operating system framework in Rust with pluggable rendering backends (PSP hardware, SDL2, UE5), window manager, virtual filesystem, and command interpreter. Includes its own CI/CD pipeline, containerized PPSSPP emulator testing, and AI code review.

### rust-psp SDK (External Repository)

The **rust-psp SDK** lives at [github.com/AndrewAltimit/rust-psp](https://github.com/AndrewAltimit/rust-psp), a modernized edition 2024 fork with safety fixes, kernel mode support, and containerized CI. Used by the OASIS_OS PSP backend as a git dependency.

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
   - Claude (security + quality) and OpenRouter automatically review the PR
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

# 5. Claude and OpenRouter review the PR:
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

| Task | Claude Code | OpenRouter | Copilot | OpenCode | Crush |
|------|------------|------------|---------|----------|--------|
| Architecture Design | Primary | No | No | Secondary | Secondary |
| Implementation | Primary | No | No | Secondary | Secondary |
| Documentation | Primary | No | No | Secondary | Secondary |
| Code Review | Primary | Primary | Secondary | Secondary | Secondary |
| Issue Triage | Secondary | No | No | Secondary | Secondary |
| Review Response | Primary | No | No | Secondary | Secondary |

Gemini and Codex are **legacy / not allowed**; see [Legacy agents](agent-matrix.md#legacy-agents-gemini-and-codex-not-allowed). The full roster by environment is in the [Agent Availability Matrix](agent-matrix.md).

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
      "review_bot_names": ["github-actions[bot]"],
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
# Build the Rust CLI tools
cd tools/rust/github-agents-cli && cargo build --release
cd tools/rust/board-manager && cargo build --release
cd tools/rust/pr-monitor && cargo build --release
cd tools/rust/markdown-link-checker && cargo build --release
cd tools/rust/code-parser && cargo build --release
cd tools/rust/automation-cli && cargo build --release

# Run issue monitor
github-agents issue-monitor

# Run PR monitor
github-agents pr-monitor

# Run refinement monitor
github-agents refinement-monitor

# Run codebase analysis (creates issues from findings)
github-agents analyze --agents claude --dry-run

# Board operations
board-manager query          # Get ready work
board-manager claim 123      # Claim an issue
board-manager release 123    # Release a claim

# PR feedback monitoring (used during development)
pr-monitor 123               # Monitor PR #123 for admin/review comments
pr-monitor 123 --timeout 600 # With custom timeout

# Markdown link checking (used in CI)
md-link-checker docs/        # Check all links in docs/

# Board work is typically triggered via GitHub Actions
# but can be tested locally via the workflow_dispatch trigger
```

**Rust CLI Tools:**

| Tool | Location | Purpose |
|------|----------|---------|
| `github-agents` | `tools/rust/github-agents-cli/` | Issue/PR monitoring, refinement, analysis |
| `board-manager` | `tools/rust/board-manager/` | GitHub Projects v2 board operations |
| `pr-monitor` | `tools/rust/pr-monitor/` | PR feedback monitoring during development |
| `gh-validator` | `tools/rust/gh-validator/` | GitHub CLI wrapper for secret masking |
| `md-link-checker` | `tools/rust/markdown-link-checker/` | Fast concurrent link validation |
| `code-parser` | `tools/rust/code-parser/` | Parse code blocks from AI responses |
| `automation-cli` | `tools/rust/automation-cli/` | Unified CI/CD orchestration, service launching, automation |
| `mcp-code-quality` | `tools/mcp/mcp_code_quality/` | Rust MCP server for code quality |

### GitHub Actions Automation

| Workflow | Purpose | Schedule |
|----------|---------|----------|
| `scheduled-agent-work.yml` | Process board work | Every 12 hours |
| `board-agent-worker.yml` | Reusable agent executor | Called by above |
| `backlog-refinement.yml` | AI insights on issues | Manual |
| `pr-review-monitor.yml` | Respond to PR feedback | Hourly + events |
| `pr-validation.yml` | Claude + OpenRouter PR reviews | PR events |

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

### For Automated Reviews
- Keep `README.md`, `CONTRIBUTING.md`, and `CLAUDE.md` accurate; reviewers read them as context
- Tune review focus in `review-profiles.yaml`
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

