# Board-Centric Agent Workflow

This document describes the end-to-end workflow for AI-assisted issue resolution, from initial issue creation through merged PR.

## Overview

All agent work flows through the **GitHub Projects v2 board** as a deliberate triage step. This ensures:

- Human oversight on what gets worked on
- Clear visibility into work queue
- Prevents agents from working on inappropriate issues
- Single source of truth for agent work status

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Board-Centric Agent Workflow                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. REFINEMENT        2. TRIAGE           3. APPROVAL                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │    Issue     │───►│  Add to      │───►│ [Approved]   │                   │
│  │  Refinement  │    │   Board      │    │   [Agent]    │                   │
│  │  (AI review) │    │  (manual)    │    │  (admin)     │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                   │                          │
│                                                   ▼                          │
│  6. MERGE             5. REVIEW           4. IMPLEMENTATION                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Human      │◄───│  AI + Human  │◄───│   Agent      │                   │
│  │  Approval    │    │   Feedback   │    │  Creates PR  │                   │
│  │  + CI Pass   │    │    Loop      │    │              │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Stage 1: Issue Refinement

**Workflow**: `backlog-refinement.yml`
**Schedule**: Manual trigger (can be scheduled)

AI agents periodically review open issues and add insights:

- **Architecture perspective**: Design considerations, patterns to use
- **Security perspective**: Potential vulnerabilities, auth requirements
- **Implementation perspective**: Suggested approach, complexity estimate
- **Maintenance perspective**: Testing needs, documentation requirements

### How It Works

1. Workflow queries issues older than N days (default: 3)
2. Multiple AI agents analyze each issue
3. Agents post comments with unique insights
4. 14-day cooldown prevents same agent re-commenting

### Configuration

```yaml
# .github/workflows/backlog-refinement.yml inputs
agents: 'claude,gemini'      # Which agents to use
max-issues: 5                # Issues per run
max-comments: 2              # Comments per issue
min-age-days: 3              # Minimum issue age
dry-run: true                # Preview without posting
enable-issue-management: false  # Allow agents to close/update issues
```

### Issue Management (Optional)

When `enable-issue-management: true`, agents can:

- Close duplicate or resolved issues
- Update unclear titles
- Add/remove labels
- Link related PRs

Maintainer comments (from `agent_admins`) get highest priority in decisions.

---

## Stage 2: Add to Board (Manual Triage)

**Action**: Manual
**Who**: Repository maintainer

After refinement, maintainers decide which issues are ready for agent work:

1. Review issue and AI insights
2. Add issue to the GitHub Projects v2 board
3. Set status to "Todo"
4. Optionally assign an agent via the "Agent" field

### Board Configuration

The board is configured in `ai-agents-board.yml`:

```yaml
project:
  owner: AndrewAltimit
  number: 1  # Your project number

columns:
  todo: "Todo"
  in_progress: "In Progress"
  blocked: "Blocked"
  done: "Done"

fields:
  agent: "Agent"           # Which agent should work on it
  priority: "Priority"     # P0, P1, P2, P3
  complexity: "Complexity" # Low, Medium, High
```

### What Makes an Issue "Ready"

An issue is considered ready for agent work when:

- Status is "Todo"
- Not blocked by other issues
- Not currently claimed by another agent
- Has `[Approved]` trigger from an `agent_admin`

---

## Stage 3: Approval

**Action**: Comment with trigger keyword
**Who**: Users in `agent_admins` list (`.agents.yaml`)

To authorize an agent to work on an issue:

```
[Approved][Claude]
```

Or let the board decide which agent:

```
[Approved]
```

### Trigger Keywords

| Keyword | Action |
|---------|--------|
| `[Approved]` | Implement the issue |
| `[Review]` | Review and provide feedback |
| `[Summarize]` | Summarize the discussion |
| `[Debug]` | Debug the issue |
| `[Close]` | Close the issue |

### Agent Selection Priority

1. **Explicit in trigger**: `[Approved][Claude]` uses Claude
2. **Board field**: Agent field on the project board item
3. **Config priority**: First available from `agent_priorities.issue_creation`

### Who Can Approve

Only users in `.agents.yaml` `security.agent_admins`:

```yaml
security:
  agent_admins:
    - AndrewAltimit  # Only humans who can trigger agent actions
```

---

## Stage 4: PR Creation

**Workflow**: `scheduled-agent-work.yml` → `board-agent-worker.yml`
**Schedule**: Every 12 hours (6 AM / 6 PM UTC)

### How It Works

1. Workflow queries board for ready work
2. Agent claims the issue (prevents conflicts)
3. Agent creates feature branch: `fix-issue-{number}-{short-id}`
4. Agent implements the fix using its tools
5. Agent creates PR linked to issue
6. Claim is released

### Claim Management

Claims prevent multiple agents from working on the same issue:

- Claims expire after 2 hours (configurable)
- Stale claims are automatically cleaned up
- Agents can renew claims for long-running work

### PR Format

The agent creates a PR with:

```markdown
## Summary
- Brief description of changes

## Test plan
- [ ] Unit tests added/updated
- [ ] Manual testing performed

Fixes #123

---
Generated by Claude via board-agent-worker
```

---

## Stage 5: AI + Human Feedback Loop

Once the PR is created, multiple feedback mechanisms engage:

### 5a. Gemini Automated Review

**Workflow**: `pr-validation.yml`
**Trigger**: PR opened/synchronized

Gemini automatically reviews every PR for:

- Security vulnerabilities
- Code quality issues
- Adherence to project standards
- Container configuration problems

Review appears as PR comment with actionable feedback.

### 5b. PR Review Monitor

**Workflow**: `pr-review-monitor.yml`
**Trigger**: Hourly + PR review events

When Gemini or humans request changes:

1. Monitor detects "changes_requested" review state
2. Parses feedback for actionable items
3. Agent implements fixes automatically
4. Commits and pushes changes
5. Comments on completion

### 5c. Human Comments

Humans can:

- Add comments with suggestions
- Request specific changes
- Ask clarifying questions

The PR Review Monitor can respond to human feedback if it contains clear action items.

### Feedback Priority

1. **Security issues**: Auto-fixed immediately
2. **Maintainer feedback**: Highest priority (from `agent_admins`)
3. **AI review feedback**: Standard priority
4. **Community feedback**: Considered but requires maintainer validation

### Auto-Fix Confidence

The agent uses a confidence system:

| Confidence | Action |
|------------|--------|
| High (>80%) | Auto-fix without asking |
| Medium (50-80%) | Fix but flag for review |
| Low (<50%) | Ask maintainer for guidance |

High-confidence issues:
- Formatting/linting errors
- Type errors with clear fixes
- Security issues with standard solutions

Low-confidence issues:
- Architectural changes
- API modifications
- Behavioral changes

---

## Stage 6: Merge

**Action**: Manual
**Who**: Repository maintainer

### Merge Requirements

A PR is ready to merge when:

1. **CI Passes**: All required checks green
2. **Reviews Approved**: No outstanding "changes_requested"
3. **Human Approval**: Maintainer approves the PR
4. **No Conflicts**: Branch is up to date with main

### Auto-Undraft

The PR Review Monitor automatically marks PRs as "Ready for Review" when:

- All CI checks pass
- No pending review changes
- Agent work is complete

### Merge Process

1. Maintainer reviews final changes
2. Approves PR via GitHub UI
3. Merges (squash recommended for clean history)
4. Issue automatically closes via "Fixes #N" reference

---

## Workflow Files Reference

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| `backlog-refinement.yml` | AI insights on issues | Manual/scheduled |
| `scheduled-agent-work.yml` | Process board work | Every 12 hours |
| `board-agent-worker.yml` | Reusable agent executor | Called by above |
| `pr-validation.yml` | Gemini PR review | PR events |
| `pr-review-monitor.yml` | Respond to feedback | Hourly + review events |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `.agents.yaml` | Agent config, security lists |
| `ai-agents-board.yml` | Board column/field mapping |
| `CLAUDE.md` | Instructions for Claude |
| `docs/agents/project-context.md` | Context for Gemini reviews |

---

## Security Model

### Separation of Concerns

```yaml
# .agents.yaml
security:
  # Can trigger [Approved][Agent] - humans only
  agent_admins:
    - AndrewAltimit

  # Comments trusted for context - includes bots
  trusted_sources:
    - AndrewAltimit
    - github-actions[bot]
    - dependabot[bot]
```

### Safety Guarantees

1. **Board gating**: Issues must be triaged before agent work
2. **Approval required**: Only `agent_admins` can trigger agents
3. **Human merge**: Final merge always requires human approval
4. **CI validation**: All changes must pass automated checks
5. **Audit trail**: All agent actions logged in issue/PR comments

---

## Example: Full Lifecycle

```bash
# Day 1: Issue Created
# User opens issue #42: "Add rate limiting to API"

# Day 4: Refinement
# backlog-refinement.yml runs
# Claude comments: "Consider token bucket algorithm, add Redis for distributed limiting"
# Gemini comments: "Security: Ensure rate limit headers are included in responses"

# Day 5: Triage
# Maintainer reviews insights, adds issue to board
# Sets Agent field to "Claude"

# Day 5: Approval
# Maintainer comments: [Approved][Claude]

# Day 5 (6 PM UTC): Implementation
# scheduled-agent-work.yml runs
# Claude claims issue, creates branch fix-issue-42-abc123
# Implements rate limiting with tests
# Creates PR #43

# Day 5: Review
# Gemini auto-reviews PR
# Requests change: "Add rate limit bypass for health checks"

# Day 5: Feedback Loop
# pr-review-monitor.yml detects feedback
# Claude implements health check bypass
# Commits and comments completion

# Day 6: Merge
# Maintainer reviews final changes
# Approves and merges PR
# Issue #42 automatically closes
```

---

## Troubleshooting

### Issue Not Being Picked Up

1. Check issue is on the board with "Todo" status
2. Verify `[Approved]` comment exists from `agent_admin`
3. Check for blocking issues
4. Review `scheduled-agent-work.yml` logs

### Agent Not Responding to Feedback

1. Check `pr-review-monitor.yml` workflow runs
2. Verify review state is "changes_requested"
3. Check agent availability (Claude auth, API keys)
4. Review feedback format (must be actionable)

### PR Stuck in Draft

1. Check all CI checks pass
2. Verify no "changes_requested" reviews
3. Review agent comments for errors
4. Manually undraft if needed

---

## Related Documentation

- [Security Model](security.md) - Detailed security documentation
- [Agent Matrix](agent-matrix.md) - Agent capabilities comparison
- [PR Monitoring](pr-monitoring.md) - PR feedback handling
- [Human Training](human-training.md) - AI safety guide
