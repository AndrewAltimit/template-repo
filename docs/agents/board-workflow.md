# Board-Centric Agent Workflow

This document describes the end-to-end workflow for AI-assisted issue resolution, from initial issue creation through merged PR.

> **PDF Version**: Build from [Agentic_Workflow_Handout.tex](Agentic_Workflow_Handout.tex) using `pdflatex` for a printable 1-page handout.

## Overview

All agent work flows through the **GitHub Projects v2 board** as a deliberate triage step. This ensures:

- Human oversight on what gets worked on
- Clear visibility into work queue
- Prevents agents from working on inappropriate issues
- Single source of truth for agent work status

### Key Principle

> **Humans decide WHAT** to work on and **WHEN** to merge.
> **Agents handle HOW** with automated quality loops.

### Main Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        AI-ASSISTED DEVELOPMENT WORKFLOW                         │
│                  Human oversight with automated agent feedback loops            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│═════════════════════════════════════════════════════════════════════════════════│
│                                FORWARD FLOW                                     │
│═════════════════════════════════════════════════════════════════════════════════│
│                      (human+agent)                                              │
│  ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐        │
│  │   Issue    │────►│  Add to    │────►│  Approve   │────►│   Agent    │        │
│  │ Refinement │     │   Board    │     │   Work     │     │ Implements │        │
│  │  (Agent)   │     │ (Human OR  │     │  (Human)   │     │  (Agent)   │        │
│  │            │     │   Agent)   │     │            │     │            │        │
│  └────────────┘     └────────────┘     └────────────┘     └────────────┘        │
│       │                  │                  │                   │               │
│       │                  │               GATE 1                 │               │
│       │                  │             (Approval)               │               │
│       ▼                  ▼                  ▼                   ▼               │
│   [Backlog]           [Todo]            [Todo]           [In Progress]          │
│                                                                 │               │
│═════════════════════════════════════════════════════════════════│═══════════════│
│                                                                 ▼               │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐       │
│   │   Merge    │◄────│   Review   │◄────│     CI     │◄────│  Create    │       │
│   │    PR      │     │   Code     │     │  Feedback  │     │    PR      │       │
│   │  (Human)   │     │  (Human)   │     │   Loop     │     │  (Agent)   │       │
│   └────────────┘     └────────────┘     └────────────┘     └────────────┘       │
│        │                  │                  ▲                   │              │
│     GATE 3             GATE 2                │                   │              │
│    (Merge)            (Review)    ┌──────────┴──────────┐        ▼              │
│        ▼                  │       │                     │   ┌────────────┐      │
│     [Done]                │       │    Auto-Fix Loop    │   │ AI Council │      │
│                           │       │   (Format/Lint)     │   │  Reviews   │      │
│                           │       │  Max 5 iterations   │   └─────┬──────┘      │
│                           │       └──────────┬──────────┘         │             │
│                           │                  ▲                    │             │
│                           │                  │                    ▼             │
│                           │                  └────────────────────┘             │
│                           │                   (review response)                 │
│                           │                                                     │
│                           └─────────────────────────────────────────────┐       │
│                                    (changes requested)                  │       │
│                                                                         ▼       │
│                                                                  ┌────────────┐ │
│                                                                  │ AI Council │ │
│                                                                  │  Re-review │ │
│                                                                  └────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

Legend: ■ Human Gate (3 total)   □ Agent Work   ◇ Review/Feedback   ○ Kanban State

Key: Humans decide WHAT to work on and WHEN to merge. Agents handle HOW.
     Both humans AND agents can add issues to the board.
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

- Issue is open and status is "Todo"
- Unassigned, or assigned to the requesting agent
- Has no excluded label (`work_queue.exclude_labels`)
- Every blocker is closed or `Done`/`Abandoned` (blockers not on the board count as unresolved)
- Not currently claimed by another agent
- Has an `[Approved][Agent]` trigger naming the requesting agent from an allowed approver (the workflows query with `board-manager ready --agent <agent> --approved-only`; see [Who Can Approve](#who-can-approve))

### Dependencies

Blocking relationships live in the board's `Blocked By` field and are managed with `board-manager`:

```bash
board-manager block 123 --blocker 120     # #120 blocks #123
board-manager unblock 123 --blocker 120   # remove it again (clears the field when empty)
board-manager deps 123                    # alias: graph
```

`deps` shows the dependency graph of an issue: its blockers (and any that are missing from the board), the issues it blocks, its parent and children (`discover-from ISSUE --parent PARENT`), and whether it is ready.

---

## Stage 3: Approval

**Action**: Comment with trigger keyword
**Who**: Users in `agent_admins` list (`.agents.yaml`)

To authorize an agent to work on an issue:

```
[Approved][Claude]
```

The trigger must name the agent. A bare `[Approved]` does not approve an issue for board work, because the workflows only pick up issues whose trigger names the agent they run as.

### Trigger Keywords

| Keyword | Action |
|---------|--------|
| `[Approved]` | Implement the issue (the only keyword that approves board work) |
| `[Review]` | Review and provide feedback |
| `[Summarize]` | Summarize the discussion |
| `[Debug]` | Debug the issue |
| `[Close]` | Close the issue |

### Agent Selection Priority

1. **Explicit in trigger**: `[Approved][Claude]` uses Claude
2. **Board field**: Agent field on the project board item
3. **Config priority**: First available from `agent_priorities.issue_creation`

### Who Can Approve

Only an `[Approved][Agent]` trigger (case-insensitive) in the issue body or a comment approves an issue, and only when written by the project owner, the repository owner, or a user in `.agents.yaml` `security.agent_admins`:

```yaml
security:
  agent_admins:
    - AndrewAltimit  # Only humans who can trigger agent actions
```

- `trusted_sources` cannot approve
- Other keywords (`[Review]`, `[Close]`, `[Summarize]`, `[Debug]`) are not approvals
- When an agent is given (`ready --agent A --approved-only`, `check-approval --agent A`, `find-approved --agent A`), the trigger must name that agent. Workflow and board names are equivalent: `[Approved][Claude]` and `[Approved][Claude Code]` both approve for `claude`
- `find-approved` verifies each search hit against these rules and drops unverified ones (`--unverified` returns raw hits)

```bash
board-manager --format json check-approval 123 --agent claude   # {approved, issue, approver}
```

---

## Stage 4: PR Creation

**Workflow**: `scheduled-agent-work.yml` → `board-agent-worker.yml`
**Schedule**: Every 12 hours (6 AM / 6 PM UTC)

### How It Works

1. Janitor releases stale claims (see below), then the workflow queries the board for ready work
2. Agent claims the issue (prevents conflicts)
3. Agent creates feature branch: `fix-issue-{number}-{short-id}`
4. Agent implements the fix using its tools
5. Agent creates PR linked to issue
6. Claim is released

### Claim Management

Claims prevent multiple agents from working on the same issue. They are structured issue comments (`[Agent Claim]`, `[Claim Renewal]`, `[Agent Release]`), and the active claim is rebuilt by replaying the last 100 comments in order:

- When two agents claim concurrently, the first comment wins; `claim` re-reads after posting and reports `lost_race` instead of proceeding
- Claims expire after `work_claims.timeout` seconds without renewal (`ai-agents-board.yml`, default 86400)
- Agents can renew claims for long-running work (`renew ISSUE --agent A --session S`)
- `release ISSUE --agent A --reason R`: `completed` (default) and `pr_created` keep the status, `blocked` sets `Blocked`, `abandoned`/`error` set `Abandoned`

**Who can claim**: only claim, renewal and release comments written by a user in `security.agent_admins` or `security.trusted_sources` of `.agents.yaml` count (case-insensitive; GitHub App authors such as the Actions bot match their `name[bot]` entry, e.g. `github-actions[bot]`). Look-alike comments from anyone else are ignored, so they cannot squat on, renew or release a claim. If `.agents.yaml` cannot be loaded, only comments by the repository owner count (fail closed). This applies to `claim`, `renew`, `janitor` and every other command that reads claims.

#### Stale Claim Cleanup (`janitor`)

```bash
board-manager --format json janitor [--agent AGENT] [--threshold HOURS] [--reset-status STATUS] [--dry-run]
```

For open `In Progress` issues, `janitor` releases claims with no activity for `HOURS` (default: `work_claims.timeout`) and resets the status (default `Todo`). Issues in progress without any claim comment are reported, not touched. `--dry-run` reports what would be cleaned without changing anything. JSON output: `{dry_run, threshold_hours, reset_status, inspected, cleaned_count, stale[], unclaimed_in_progress[], failed[]}`.

`board-agent-worker.yml` and the `board-agent-work` action run `janitor --agent <agent> --threshold <stale-claim-threshold>` (default 2 hours) before querying for ready work and report `cleaned_count` as the `stale-claims-cleaned` output. A janitor failure is logged as a warning and never blocks picking up new work.

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

Once the PR is created, multiple feedback mechanisms engage in a **tight automated loop**.

### Agent Council

Multiple AI agents provide diverse review perspectives:

```
┌────────────────────────────────────────────────────────────────┐
│                       AGENT COUNCIL                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│   │   Gemini    │     │   Codex     │     │   Claude    │      │
│   │  (Review)   │     │  (Review)   │     │   (Fix)     │      │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘      │
│          │                   │                   │             │
│          │    Security &     │   Code Quality    │             │
│          │   Architecture    │    & Patterns     │             │
│          │                   │                   │             │
│          └───────────────────┴───────────────────┘             │
│                              │                                 │
│                              ▼                                 │
│                    ┌─────────────────┐                         │
│                    │  Consolidated   │                         │
│                    │    Feedback     │                         │
│                    └─────────────────┘                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Note: Reviews are NOT weighted equally.
Maintainer feedback > AI suggestions > Community feedback
```

### 5a. Gemini Automated Review

**Workflow**: `pr-validation.yml`
**Trigger**: PR opened/synchronized

Gemini automatically reviews every PR for:

- Security vulnerabilities
- Code quality issues
- Adherence to project standards
- Container configuration problems

Review appears as PR comment with actionable feedback.

### 5b. Codex Automated Review

**Workflow**: `pr-validation.yml`
**Trigger**: PR opened/synchronized

Codex provides complementary review focusing on:

- Code patterns and best practices
- Performance considerations
- API design feedback

### 5c. Inline Agent Review Response (NEW)

**Workflow**: `pr-validation.yml` → `agent-review-response` job
**Trigger**: Immediately after Gemini/Codex reviews complete

```
┌─────────────────────────────────────────────────────────────────┐
│                  TIGHT FEEDBACK LOOP 1                          │
│                  (Review Response)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │   Gemini    │────►│   Cleanup   │────►│   Codex     │        │
│  │   Review    │     │   Working   │     │   Review    │        │
│  │             │     │    Dir      │     │             │        │
│  └─────────────┘     └─────────────┘     └──────┬──────┘        │
│                                                 │               │
│                                                 ▼               │
│                                          ┌─────────────┐        │
│                                          │   Cleanup   │        │
│                                          │   Working   │        │
│                                          │    Dir      │        │
│                                          └──────┬──────┘        │
│                                                 │               │
│                                                 ▼               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │   Push      │◄────│   Claude    │◄────│  Download   │        │
│  │   Changes   │     │  Auto-Fix   │     │  Artifacts  │        │
│  └──────┬──────┘     └─────────────┘     └─────────────┘        │
│         │                                                       │
│         │         (Re-triggers pipeline)                        │
│         └──────────────────────────────────────────────────►    │
│                                                                 │
│  Reviews always run on all commits.                             │
│  Agent evaluates if there are new/unaddressed issues to fix.    │
│  Safety: Max 5 iterations per PR                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**How It Works:**

1. Gemini completes review, working directory cleaned
2. Codex downloads Gemini artifact and completes review, working directory cleaned
3. Agent-review-response downloads review artifacts
4. Claude parses review artifacts for actionable feedback
5. Autoformat runs first (black, isort)
6. Claude fixes remaining lint/format issues
7. Changes committed by agent (detected via author name)
8. Push retriggers pipeline; reviews run again but agent evaluates if new issues exist

### 5d. CI Failure Handler (NEW)

**Workflow**: `pr-validation.yml` → `agent-failure-handler` job
**Trigger**: When format-check, basic-lint, or full-lint fails

```
┌─────────────────────────────────────────────────────────────────┐
│                  TIGHT FEEDBACK LOOP 2                          │
│                  (CI Failure Handler)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │  Format/    │────►│  Autoformat │────►│   Claude    │        │
│  │  Lint Fail  │     │   (black,   │     │  Fixes      │        │
│  │             │     │   isort)    │     │  Remaining  │        │
│  └─────────────┘     └─────────────┘     └──────┬──────┘        │
│                                                 │               │
│                                                 ▼               │
│                                          ┌─────────────┐        │
│                                          │    Push     │        │
│                                          │  Changes    │        │
│       ◄──────────────────────────────────┴─────────────┘        │
│       │         (Re-triggers pipeline)                          │
│       ▼                                                         │
│  ┌─────────────┐                                                │
│  │   CI Runs   │  Fixed issues should pass                      │
│  │   Again     │                                                │
│  └─────────────┘                                                │
│                                                                 │
│  Handles: formatting, linting, type errors, unused imports      │
│  Does NOT handle: test failures, build errors                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Scope (Safe Categories):**

- Formatting issues (ruff format)
- Linting errors (ruff)
- Type errors (mypy)
- Unused imports

**Out of Scope (Requires Human):**

- Test failures (may indicate logic bugs)
- Build failures (may require architecture decisions)

### 5e. Human Comments

Humans can:

- Add comments with suggestions
- Request specific changes
- Ask clarifying questions

The PR Review Monitor can respond to human feedback if it contains clear action items.

### Loop Prevention

Multiple safety mechanisms prevent infinite loops:

| Mechanism | Description |
|-----------|-------------|
| **Always Review** | Reviews run on all commits; agent decides whether to act on feedback |
| **Clean Slate** | Working directory cleaned between reviewers to ensure consistency |
| **Iteration Counter** | Max 5 iterations via workflow artifacts |
| **Human Reset** | Counter resets when human pushes |
| **Smart Agent** | Agent checks if issues are new/unaddressed before committing |

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
2. **Approval required**: Only `agent_admins` (and the project/repository owner) can approve, with an `[Approved][Agent]` trigger naming the agent
3. **Trusted claims**: Only claim comments from `agent_admins`/`trusted_sources` are honoured
4. **Human merge**: Final merge always requires human approval
5. **CI validation**: All changes must pass automated checks
6. **Audit trail**: All agent actions logged in issue/PR comments

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
2. Verify an `[Approved][Agent]` comment naming the agent exists from an `agent_admin` (`board-manager check-approval ISSUE --agent AGENT`)
3. Check for blocking issues (`board-manager deps ISSUE`)
4. Check for a stale claim by another agent (`board-manager janitor --dry-run`)
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
