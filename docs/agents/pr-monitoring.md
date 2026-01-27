# PR Monitoring System

## Overview

The PR Monitoring System allows Claude Code to continuously monitor Pull Requests for new comments from administrators and AI reviewers (like Gemini), automatically detecting when responses are needed.

## Architecture

The system uses a single Rust binary:

```
pr-monitor (Rust binary)
    ↓
Claude Code (Main agent responder)
```

**pr-monitor**: Rust CLI tool that polls GitHub for comments, classifies them, and outputs structured JSON decisions.

## Installation

### Build from source

```bash
cd tools/rust/pr-monitor
cargo build --release
```

The binary will be at `target/release/pr-monitor`.

### Using Docker (CI)

```bash
docker compose --profile ci run --rm rust-ci cargo build --release -p pr-monitor
```

## Usage

### Command Line

```bash
# Basic monitoring (10 minute timeout, 5 second poll interval)
./tools/rust/pr-monitor/target/release/pr-monitor 48

# With custom timeout (30 minutes)
./tools/rust/pr-monitor/target/release/pr-monitor 48 --timeout 1800

# JSON output only (for automation)
./tools/rust/pr-monitor/target/release/pr-monitor 48 --json

# Monitor comments after a specific commit
./tools/rust/pr-monitor/target/release/pr-monitor 48 --since-commit abc1234

# Custom poll interval (check every 10 seconds)
./tools/rust/pr-monitor/target/release/pr-monitor 48 --poll-interval 10

# Combine options
./tools/rust/pr-monitor/target/release/pr-monitor 48 --since-commit abc1234 --timeout 1800 --json
```

### In Claude Code

When working with PRs, you can end tasks with:
- "...and monitor the PR for new comments"
- "...then watch for admin responses"
- "...and wait for Gemini's review"

Claude will automatically start the monitoring tool.

### Programmatic Usage

```bash
# Run monitor and capture JSON output
result=$(./tools/rust/pr-monitor/target/release/pr-monitor 48 --json 2>/dev/null)

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
  "comment": {
    "author": "AndrewAltimit",
    "timestamp": "2025-08-09T14:59:45Z",
    "body": "[ADMIN] Command text here..."
  }
}
```

### Response Types

| Type | Author | Trigger | Priority | Needs Response |
|------|--------|---------|----------|----------------|
| `admin_command` | Admin user | Contains `[ADMIN]` | High | Yes |
| `admin_comment` | Admin user | Any comment | Normal | Yes |
| `gemini_review` | github-actions | Contains "Gemini" | Normal | Yes |
| `ci_results` | github-actions | Contains "PR Validation Results" | Low | No |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Found relevant comment (JSON on stdout) |
| 1 | Timeout or error |
| 130 | Interrupted by user (Ctrl+C) |

## Configuration

The monitor checks for comments from:
- **AndrewAltimit** (repository admin)
- **github-actions** (bot comments, including Gemini reviews)

Monitoring parameters:
- Default poll interval: 5 seconds
- Default timeout: 10 minutes (600 seconds)
- Configurable via `--poll-interval` and `--timeout` flags

## Commit-Based Monitoring

The PR monitoring system supports starting from a specific commit, which is useful after pushing changes:

### Use Cases

1. **After pushing commits**: Monitor only for feedback on your new changes
2. **Resuming monitoring**: Start from where you left off
3. **Filtering old comments**: Ignore comments that predate your work

### How It Works

When you specify `--since-commit SHA`, the monitor:
1. Gets the timestamp of the specified commit via GitHub API
2. Filters out any comments created before that timestamp
3. Only returns comments relevant to changes after that commit

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
     ./tools/rust/pr-monitor/target/release/pr-monitor 48 --since-commit abc1234

  Or monitor all new comments:
     ./tools/rust/pr-monitor/target/release/pr-monitor 48

This will watch for:
  - Admin comments and commands
  - Gemini AI code review feedback
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
[Responds when admin/Gemini comments]
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
  "needs_response": false,
  "priority": "low",
  "response_type": "ci_results",
  "action_required": "Review CI results if failures present",
  "comment": {
    "author": "github-actions[bot]",
    "timestamp": "2025-01-15T10:30:00Z",
    "body": "## PR Validation Results\n\nAll checks passed!"
  }
}
```

## Best Practices

1. **Use --json for Automation**: Always use `--json` flag when integrating with scripts
2. **Check Priority**: High priority (admin commands) should be addressed immediately
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
./tools/rust/pr-monitor/target/release/pr-monitor 48 --timeout 3600  # 1 hour
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
- No other runtime dependencies (statically linked Rust binary)

### Security Considerations

- Only responds to authorized users (admin, github-actions)
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
   - Gemini reviews typically arrive within 2-5 minutes
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
