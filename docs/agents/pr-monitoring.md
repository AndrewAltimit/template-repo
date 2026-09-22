# PR Monitoring System

## Overview

The PR Monitoring System allows Claude Code to continuously monitor Pull Requests for new comments and reviews from administrators and AI reviewers (the Claude and OpenRouter review pipeline, GitHub Copilot code review, the Claude GitHub App), automatically detecting when responses are needed.

The authoritative reference is [`tools/rust/pr-monitor/README.md`](../../tools/rust/pr-monitor/README.md).

## Architecture

The system uses a single Rust binary:

```
pr-monitor (Rust binary)
    ↓
Claude Code (Main agent responder)
```

**pr-monitor**: Rust CLI tool that polls GitHub (one GraphQL query per poll covering conversation comments, submitted PR reviews with their inline comments, the PR state and the head SHA), classifies new items, and outputs structured JSON decisions.

## Installation

### Build and install

```bash
tools/rust/pr-monitor/install.sh      # builds if needed, copies to ~/.local/bin
tools/rust/pr-monitor/uninstall.sh    # removes it again
```

### Build from source

```bash
cd tools/rust/pr-monitor
cargo build --release
```

The binary will be at `target/release/pr-monitor`.

### Using Docker (CI)

```bash
docker compose --profile ci run --rm -w /app/tools/rust/pr-monitor rust-ci cargo build --release
```

## Usage

### Command Line

```bash
# Basic monitoring (10 minute timeout, 5 second poll interval)
pr-monitor 48

# With custom timeout (30 minutes)
pr-monitor 48 --timeout 1800

# JSON output only (quiet mode, no stderr progress)
pr-monitor 48 --json

# Monitor comments after a specific commit (reports existing feedback immediately)
pr-monitor 48 --since-commit abc1234

# Local refs work too (resolved with git)
pr-monitor 48 --since-commit HEAD

# Wait specifically for an AI code review
pr-monitor 48 --type ai_agent_review

# One-shot check: is anything already waiting after this commit?
pr-monitor 48 --since-commit abc1234 --timeout 0

# Distinguish "timed out" (exit 2) from "error" (exit 1)
pr-monitor 48 --timeout-exit-code 2

# Custom poll interval (check every 10 seconds)
pr-monitor 48 --poll-interval 10

# Watch a different repository
pr-monitor 48 --repo AndrewAltimit/template-repo

# Combine options
pr-monitor 48 --since-commit abc1234 --timeout 1800 --json
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `<PR_NUMBER>` | (required) | Pull request number to monitor |
| `--timeout <SECONDS>` | `600` | How long to wait. `0` checks existing comments once and exits |
| `--poll-interval <SECONDS>` | `5` | Delay between polls (minimum 1) |
| `--json` | off | Suppress progress output on stderr (warnings and errors still print) |
| `--since-commit <SHA>` | none | Only consider comments created after this commit's committer date. Accepts a SHA (looked up via the GitHub API, falling back to local git for unpushed commits) or a local ref such as `HEAD` |
| `-R`, `--repo <OWNER/REPO>` | current repo | Repository to monitor (otherwise resolved by `gh` from the current directory or `GH_REPO`) |
| `--admin-user <LOGIN>` | `AndrewAltimit` | Admin login. Also read from `PR_MONITOR_ADMIN_USER` |
| `--author <LOGIN>` | admin + bots | Only watch these authors (repeatable or comma-separated). Replaces the default set; other comments from these authors are reported as `user_comment` |
| `--type <TYPE>` | all | Only report these response types (repeatable or comma-separated): `admin_command`, `admin_comment`, `admin_approval`, `ai_agent_review`, `ci_results`, `user_comment` |
| `--timeout-exit-code <CODE>` | `1` | Exit code used when the timeout expires (1-255) |
| `--compact` | off | Print the JSON decision on one line instead of pretty-printed |

`--config` is still accepted for backwards compatibility but ignored.

### In Claude Code

When working with PRs, you can end tasks with:
- "...and monitor the PR for new comments"
- "...then watch for admin responses"
- "...and wait for the AI review"

Claude will automatically start the monitoring tool.

### Programmatic Usage

```bash
# Run monitor and capture JSON output
result=$(pr-monitor 48 --json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "Relevant comment found:"
    echo "$result" | jq .
fi
```

## Response Structure

The monitoring tool returns structured JSON:

```json
{
  "needs_response": true,
  "priority": "high",
  "response_type": "admin_command",
  "action_required": "Execute admin command and respond",
  "review_metadata": {
    "trigger_action": "fix",
    "trigger_agent": "claude"
  },
  "comment": {
    "author": "AndrewAltimit",
    "timestamp": "2026-06-05T12:38:22+00:00",
    "body": "[Fix][Claude] Please address the lint failures",
    "id": "IC_kwDO...",
    "kind": "issue_comment",
    "url": "https://github.com/AndrewAltimit/template-repo/pull/48#issuecomment-..."
  },
  "pr_number": 48,
  "head_sha": "0e947271ea5765549ce7a757fced4ca7cbbca883"
}
```

The core fields (`needs_response`, `priority`, `response_type`, `action_required`, `comment.{author,timestamp,body}`) match the original Python implementation; all other fields are additive and omitted when empty.

| Field | Description |
|-------|-------------|
| `needs_response`, `priority`, `response_type`, `action_required` | Classification (see table below) |
| `comment.author`, `comment.timestamp`, `comment.body` | The triggering comment or review |
| `comment.id`, `comment.kind`, `comment.url` | GraphQL node ID, `issue_comment` or `review`, permalink |
| `review_metadata.commit_sha` | Commit from the review marker (or the commit a PR review was submitted on) |
| `review_metadata.review_id` | Timestamp-based review identifier |
| `review_metadata.reviewer` | Reviewer slug: `claude`, `openrouter`, `copilot`, ... |
| `review_metadata.review_state` | For PR reviews: `APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, `DISMISSED` |
| `review_metadata.inline_comments` | For PR reviews: `[{author, path, line, body, url}]` |
| `review_metadata.outdated` | `true` when the reviewed commit is no longer the PR head |
| `review_metadata.already_responded` | `true` when a review-fix agent comment (or legacy response marker) already follows the review |
| `review_metadata.trigger_action`, `trigger_agent` | Parsed `[Action][Agent]` trigger |
| `review_metadata.failed_checks` | Failed rows of a CI results table |
| `pr_number`, `head_sha` | PR number and head commit at detection time |

### Response Types

| Type | Author | Trigger | Priority | Needs Response |
|------|--------|---------|----------|----------------|
| `admin_command` | Admin | `[Action]` / `[Action][Agent]` trigger (`approved`, `review`, `close`, `summarize`, `debug`, `fix`, `implement`) or legacy `[ADMIN]` | High | Yes |
| `admin_comment` | Admin | Any other comment, a review with a body or inline comments, or a *changes requested* review (High) | Normal / High | Yes |
| `admin_approval` | Admin | Approving review with no body or inline comments | Normal | No |
| `ai_agent_review` | github-actions, Claude App | `## {Agent} AI ... Review` heading or `<!-- {agent}-review-marker[:commit:SHA] -->` | Normal | Yes |
| `ai_agent_review` | Copilot | Any submitted Copilot review; "generated no comments" reviews are Low / no response | Normal / Low | Yes / No |
| `ci_results` | github-actions | `PR Validation Results` table; any `fail` row makes it actionable | Low / Normal | No / Yes |
| `user_comment` | `--author` logins | Any other non-empty comment from an explicitly watched author | Normal | Yes |

Comments carrying agent markers (`<!-- agent-metadata:... -->`, `<!-- ai-agent-*-response:... -->`, "Generated with [Claude Code]") are never reported, whoever posted them: the review-response agents post with the admin's token. Markers from retired reviewers (for example `gemini-review-marker`, `codex-review-marker`) still parse, so old PRs classify correctly.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Found relevant comment (JSON on stdout) |
| 1 | Timeout or error (no relevant comment found); stdout is empty |
| `--timeout-exit-code` | Timeout, when configured to something other than 1 |
| 2 | Invalid command-line arguments (from the argument parser) |
| 130 | Interrupted by user (Ctrl+C) |

## Configuration

By default the monitor watches:
- the **admin user** (`--admin-user`, default **AndrewAltimit**)
- **github-actions** (Claude / OpenRouter review pipeline and the `PR Validation Results` table)
- **GitHub Copilot** code review (`copilot-pull-request-reviewer`)
- the **Claude GitHub App** (`claude[bot]`)

Login matching is case-insensitive and ignores the `[bot]` suffix. `--author` replaces this set.

Monitoring parameters:
- Default poll interval: 5 seconds (minimum 1)
- Default timeout: 10 minutes (600 seconds); `0` checks once and exits
- Configurable via `--poll-interval` and `--timeout` flags
- Transient failures and rate limits are retried with back-off (up to 60 s); monitoring aborts after 5 consecutive failures, or immediately on authentication errors or an unknown PR

### Phases

1. **Backlog check** (only with `--since-commit`): comments and reviews created after the commit that *need a response* are reported immediately. Informational items (passing CI tables, bare approvals) are skipped here so restarting the monitor does not return the same non-actionable item again.
2. **Live polling**: everything present at start is the baseline. Any new, recognised item that passes the filters is reported, including informational ones such as a passing CI table (use `--type` to narrow this). If several arrive in one poll, the most urgent wins (priority, then oldest).

## Commit-Based Monitoring

The PR monitoring system supports starting from a specific commit, which is useful after pushing changes:

### Use Cases

1. **After pushing commits**: Monitor only for feedback on your new changes
2. **Resuming monitoring**: Start from where you left off
3. **Filtering old comments**: Ignore comments that predate your work

### How It Works

When you specify `--since-commit SHA`, the monitor:
1. Gets the committer date of the specified commit via the GitHub API (falling back to local git for unpushed commits or refs such as `HEAD`)
2. Filters out any comments and reviews created before that timestamp
3. Immediately reports existing feedback after that commit that needs a response, then keeps watching for new items

If the commit cannot be resolved, a warning is printed and only new comments are watched.

### Automatic Detection with Hooks

The repository includes a pre-push hook that automatically:
1. Detects when you push commits
2. Identifies the current PR
3. Suggests the monitoring command with the pushed commit SHA
4. Reminds you to monitor for feedback

Example output after `git push`:
```
============================================================
PR FEEDBACK MONITORING REMINDER
============================================================

You're pushing commits to PR #48 on branch 'feature-branch'.
After push completes, consider monitoring for feedback:

  Monitor from this commit onwards:
     pr-monitor 48 --since-commit abc1234

  Or monitor all new comments:
     pr-monitor 48

This will watch for:
  - Admin comments and commands
  - AI agent code review feedback
  - CI/CD validation results

The monitor will return structured JSON when relevant comments are detected.
============================================================
```

## Integration with Claude Code

### Automatic Monitoring

Claude can automatically start monitoring when:
1. A PR-related task is completed
2. The user mentions "monitor" or "watch" in their request
3. An admin command requires follow-up

## Examples

### Example 1: Monitor After PR Update

```
User: Update the PR with the fixes and monitor for reviews

Claude: I'll update the PR and then monitor for feedback.
[Makes changes and pushes]
[Starts monitoring]
[Responds when admin or AI reviewer comments]
```

### Example 2: Direct Monitoring

```
User: Monitor PR #48 for new comments

Claude: Starting PR #48 monitoring...
[Runs monitoring tool]
[Detects admin comment]
Claude: Admin posted: "[ADMIN] Please add tests"
[Implements tests and responds]
```

### Example 3: JSON Output

```json
{
  "needs_response": true,
  "priority": "normal",
  "response_type": "ci_results",
  "action_required": "Investigate and fix failing CI checks",
  "review_metadata": {
    "failed_checks": ["Full lint", "Test suite"]
  },
  "comment": {
    "author": "github-actions",
    "timestamp": "2026-06-05T10:30:00+00:00",
    "body": "## PR Validation Results\n...",
    "id": "IC_kwDO...",
    "kind": "issue_comment",
    "url": "https://github.com/AndrewAltimit/template-repo/pull/48#issuecomment-..."
  },
  "pr_number": 48,
  "head_sha": "0e947271ea5765549ce7a757fced4ca7cbbca883"
}
```

A CI table with no failed rows is reported as `needs_response: false`, priority `low`, action "Review CI results if failures present".

## Best Practices

1. **Use --json for Automation**: Always use `--json` flag when integrating with scripts (add `--compact` for single-line output)
2. **Check Priority**: High priority (admin commands, changes-requested reviews) should be addressed immediately
3. **Timeout Appropriately**: Set longer timeouts for complex reviews (30-60 minutes)
4. **Monitor Specific PRs**: Always specify PR number to avoid confusion
5. **Use Commit Filtering**: Use `--since-commit` after pushing to focus on new feedback

## Troubleshooting

### Monitor Not Detecting Comments

1. Check GitHub CLI authentication: `gh auth status`
2. Verify PR exists: `gh pr view PR_NUMBER`
3. Build the tool: `cd tools/rust/pr-monitor && cargo build --release`

### Timeout Issues

Increase timeout for long-running reviews:
```bash
pr-monitor 48 --timeout 3600  # 1 hour
```

### Graceful Shutdown

Press Ctrl+C to interrupt monitoring. The tool will exit with code 130.

## Implementation Details

### File Locations

```
tools/rust/pr-monitor/
├── Cargo.toml
├── README.md
└── src/
    ├── main.rs           # CLI entry point
    ├── lib.rs            # Library exports
    ├── cli.rs            # clap argument parsing
    ├── error.rs          # Error types with help text
    ├── github/           # GitHub API client (via gh CLI)
    ├── monitor/          # Polling loop logic
    └── analysis/         # Comment classification
```

### Required Dependencies

- **gh** (GitHub CLI) - Must be installed and authenticated
- **git** - Only used to resolve `--since-commit` refs that are not on GitHub
- No other runtime dependencies

### Security Considerations

- Only reports comments from the watched authors (admin, github-actions, Copilot, Claude App, or the explicit `--author` set)
- Comments with agent markers are ignored, so agents posting with the admin's token are never mistaken for admin feedback
- No credentials stored in binary
- Uses GitHub CLI authentication
- Timeouts prevent infinite loops

## Best Practices for Tight Feedback Loops

### For Developers Pair Programming with AI Agents

1. **Start monitoring immediately after pushing**:
   - Use the commit SHA from your push to filter comments
   - This ensures you only see feedback relevant to your changes

2. **Keep monitoring sessions short and focused**:
   - Use appropriate timeouts (5-15 minutes for quick reviews)
   - Longer timeouts (30-60 minutes) for comprehensive reviews

3. **Use the hook system**:
   - The pre-push hook automatically reminds you to monitor
   - Shows the exact command with the right commit SHA

4. **Combine with CI/CD**:
   - Monitor for both human and automated feedback
   - AI agent reviews typically arrive within 2-5 minutes
   - Admin comments may take longer

### Interactive Mode Workflow

```bash
# 1. Make changes
claude code> "Fix the linting issues in PR #48"

# 2. Push changes (hook activates)
[Git push detected - monitoring reminder shown]

# 3. Start monitoring from pushed commit
claude code> "Monitor PR #48 from commit abc1234"

# 4. Receive and act on feedback
[Admin comment detected: "Please add tests"]

# 5. Iterate quickly
claude code> "Add the requested tests and push"
```

## Future Enhancements

1. **WebSocket Monitoring**: Real-time updates instead of polling
2. **Multiple PR Support**: Monitor several PRs simultaneously
3. **Custom Triggers**: Configure additional users/keywords via config file
4. **Notification System**: Desktop/email alerts
5. **Pattern Matching**: Regex-based response triggers
