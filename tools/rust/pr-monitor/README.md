# pr-monitor

> A Rust CLI tool that waits for actionable feedback on a GitHub pull request and prints a structured JSON decision.

## Overview

`pr-monitor` watches a pull request for comments and reviews from the repository admin and from AI reviewers (the Claude and OpenRouter review pipeline, GitHub Copilot code review, the Claude GitHub App). When a relevant item shows up it prints a JSON decision on stdout and exits `0`, so an agent can block on it:

```bash
decision=$(pr-monitor 48 --since-commit "$(git rev-parse HEAD)" --json) && echo "$decision" | jq .
```

## Features

- **One API call per poll** - a single GraphQL query fetches conversation comments, submitted PR reviews (with their inline comments), the PR state and the head SHA
- **Robust change detection** - new items are tracked by node ID, so deleted or edited comments and several comments arriving at once are handled correctly
- **Reviews, not just comments** - PR reviews (approve / request changes / comment) and inline diff comments are covered, including GitHub Copilot reviews
- **Intelligent classification** - admin commands, admin feedback, admin approvals, AI reviews, CI results (with failed checks extracted)
- **Ignores agent chatter** - comments posted by automation agents with the admin's token (`<!-- agent-metadata:... -->`, legacy `ai-agent-*-response` markers, the Claude Code footer) are not treated as admin feedback
- **Commit-based filtering** - `--since-commit` reports feedback already posted after a commit, then keeps watching
- **Filtering** - by response type (`--type`) and author (`--author`)
- **Resilient polling** - transient failures and rate limits are retried with back-off; auth errors and unknown PRs fail fast
- **Graceful shutdown** - Ctrl+C is honoured within 100 ms, exit code 130

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

```bash
# Basic monitoring (10 minute timeout, 5 second poll interval)
pr-monitor 123

# Monitor for 30 minutes
pr-monitor 123 --timeout 1800

# JSON-only output (quiet mode, no stderr progress)
pr-monitor 123 --json

# Only feedback after a specific commit (reports existing feedback immediately)
pr-monitor 123 --since-commit abc1234

# Local refs work too (resolved with git)
pr-monitor 123 --since-commit HEAD

# Wait specifically for an AI code review
pr-monitor 123 --type ai_agent_review

# One-shot check: is anything already waiting after this commit?
pr-monitor 123 --since-commit abc1234 --timeout 0

# Distinguish "timed out" (exit 2) from "error" (exit 1)
pr-monitor 123 --timeout-exit-code 2

# Watch a different repository
pr-monitor 123 --repo AndrewAltimit/template-repo

# Combined options
pr-monitor 123 --timeout 3600 --poll-interval 10 --json --since-commit abc1234
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `<PR_NUMBER>` | (required) | Pull request number to monitor |
| `--timeout <SECONDS>` | `600` | How long to wait. `0` checks existing comments once and exits |
| `--poll-interval <SECONDS>` | `5` | Delay between polls (minimum 1) |
| `--json` | off | Suppress progress output on stderr (warnings and errors still print) |
| `--since-commit <SHA>` | none | Only consider comments created after this commit's committer date. Accepts a SHA (looked up via the GitHub API, falling back to local git for unpushed commits) or a local ref such as `HEAD`. Existing comments after the commit that need a response are reported immediately. If the commit cannot be resolved a warning is printed and only new comments are watched |
| `-R`, `--repo <OWNER/REPO>` | current repo | Repository to monitor (otherwise resolved by `gh` from the current directory or `GH_REPO`) |
| `--admin-user <LOGIN>` | `AndrewAltimit` | Admin login. Also read from `PR_MONITOR_ADMIN_USER` |
| `--author <LOGIN>` | admin + bots | Only watch these authors (repeatable or comma-separated). Replaces the default set; comments from these authors that match no other category are reported as `user_comment` |
| `--type <TYPE>` | all | Only report these response types (repeatable or comma-separated): `admin_command`, `admin_comment`, `admin_approval`, `ai_agent_review`, `ci_results`, `user_comment` |
| `--timeout-exit-code <CODE>` | `1` | Exit code used when the timeout expires (1-255) |
| `--compact` | off | Print the JSON decision on one line instead of pretty-printed |
| `-h`, `--help` / `-V`, `--version` | | Help / version |

`--config` is still accepted for backwards compatibility but ignored (it was never implemented).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Found relevant comment (JSON output on stdout) |
| 1 | Timeout or error (no relevant comment found); stdout is empty |
| `--timeout-exit-code` | Timeout, when configured to something other than 1 |
| 2 | Invalid command-line arguments (from the argument parser) |
| 130 | Interrupted by user (Ctrl+C) |

## What Gets Reported

By default the monitor watches:

- the **admin user** (`--admin-user`)
- **github-actions** - Claude / OpenRouter review pipeline and the `PR Validation Results` table
- **GitHub Copilot** code review (`copilot-pull-request-reviewer`)
- the **Claude GitHub App** (`claude[bot]`)

Login matching is case-insensitive and ignores the `[bot]` suffix.

### Phases

1. **Backlog check** (only with `--since-commit`): comments and reviews created after the commit that *need a response* are reported immediately. Older pages are fetched if the newest window does not reach back far enough. Informational items (passing CI tables, bare approvals) are skipped here so restarting the monitor does not return the same non-actionable item again.
2. **Live polling**: everything present at start is the baseline. Any new, recognised item that passes the filters is reported, including informational ones such as a passing CI table (use `--type` to narrow this). If several arrive in one poll the most urgent wins (priority, then oldest).

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

Comments carrying agent markers (`<!-- agent-metadata:... -->`, `<!-- ai-agent-*-response:... -->`, "Generated with [Claude Code]") are never reported, whoever posted them: the review-response agents post with the admin's token.

Markers from retired reviewers (for example `gemini-review-marker`, `codex-review-marker`) still parse, so old PRs classify correctly.

## Output Format

The core fields match the original Python implementation; all other fields are additive and omitted when empty.

```json
{
  "needs_response": true,
  "priority": "normal",
  "response_type": "ai_agent_review",
  "action_required": "Address AI agent code review feedback",
  "review_metadata": {
    "commit_sha": "0e947271ea5765549ce7a757fced4ca7cbbca883",
    "review_id": "2026-06-05-12-38-22",
    "reviewer": "openrouter"
  },
  "comment": {
    "author": "github-actions",
    "timestamp": "2026-06-05T12:38:22+00:00",
    "body": "## Openrouter AI Incremental General Review\n...",
    "id": "IC_kwDO...",
    "kind": "issue_comment",
    "url": "https://github.com/AndrewAltimit/template-repo/pull/326#issuecomment-4631611922"
  },
  "pr_number": 326,
  "head_sha": "0e947271ea5765549ce7a757fced4ca7cbbca883"
}
```

| Field | Description |
|-------|-------------|
| `needs_response`, `priority`, `response_type`, `action_required` | Classification (see table above) |
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

## API Usage and Limits

- Each poll is one GraphQL request (about 1 point of the 5,000/hour GraphQL budget), so the default 5 s interval uses roughly 720 points per hour.
- Each poll fetches the newest 100 conversation comments and newest 50 reviews (up to 100 inline comments each). Live detection only needs the newest items; the `--since-commit` backlog check pages further back (up to 10 pages per list).
- Transient failures (network errors, 5xx, GraphQL errors) are retried with exponential back-off up to 60 s; rate limits wait at least 60 s. Monitoring aborts after 5 consecutive failures, or immediately on authentication errors or an unknown PR.
- When stderr is not a terminal (for example when an agent captures it), progress is printed as a plain line once a minute instead of a constantly rewritten status line.

## Requirements

The tool uses the `gh` CLI for GitHub API access, which must be installed and authenticated:

```bash
gh auth status   # check
gh auth login    # authenticate if needed
```

No other runtime dependencies. `git` is used only to resolve `--since-commit` refs that are not on GitHub.

## Library Use

The crate also exposes a library (`pr_monitor`): `classify` for comment classification, `Filter` and `Poller` for monitoring, and the `PrSource` trait so the polling loop can run against any data source.

## Development

```bash
# From the repository root (container-first)
docker compose --profile ci run --rm -w /app/tools/rust/pr-monitor rust-ci \
  bash -c "cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test"
```

Tests cover classification, GraphQL response parsing, the polling loop (against a scripted in-memory source) and the binary end to end (against a fake `gh` script, Unix only).

## History

This tool is a Rust port of the original Python/Bash implementation (`automation/monitoring/pr/`), keeping the same core JSON output for drop-in compatibility.

## License

Part of the template-repo project. See repository LICENSE file.
