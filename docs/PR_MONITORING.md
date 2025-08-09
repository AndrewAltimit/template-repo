# PR Monitoring System

## Overview

The PR Monitoring System allows Claude Code to continuously monitor Pull Requests for new comments from administrators and AI reviewers (like Gemini), automatically detecting when responses are needed.

## Architecture

The system uses a hierarchical agent design:

```
monitor.sh (Low-level detector)
    ↓
pr_monitor_agent.py (Subagent analyzer)
    ↓
Claude Code (Main agent responder)
```

1. **monitor.sh**: Bash script that polls GitHub for new comments
2. **pr_monitor_agent.py**: Python agent that analyzes comments and decides action
3. **Claude Code**: Main agent that receives structured data and responds

## Usage

### Command Line

```bash
# Basic monitoring
./scripts/pr-monitoring/monitor-pr 48

# With custom timeout (30 minutes)
./scripts/pr-monitoring/monitor-pr 48 --timeout 1800

# JSON output only (for automation)
./scripts/pr-monitoring/monitor-pr 48 --json
```

### In Claude Code

When working with PRs, you can end tasks with:
- "...and monitor the PR for new comments"
- "...then watch for admin responses"
- "...and wait for Gemini's review"

Claude will automatically start the monitoring agent.

### Programmatic Usage

```python
import subprocess
import json

# Run monitor and get structured response
result = subprocess.run(
    ["./scripts/pr-monitoring/monitor-pr", "48", "--json"],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    data = json.loads(result.stdout)
    if data["needs_response"]:
        print(f"Action required: {data['action_required']}")
```

## Response Structure

The monitoring agent returns structured JSON:

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

- **admin_command**: Admin message with [ADMIN] tag (high priority)
- **admin_comment**: Regular admin comment (normal priority)
- **gemini_review**: Gemini AI code review (normal priority)
- **ci_results**: CI/CD validation results (informational)

## Configuration

The monitor checks for comments from:
- **AndrewAltimit** (repository admin)
- **github-actions** (bot comments, including Gemini reviews)

Monitoring intervals:
- Checks every 5 seconds
- Default timeout: 10 minutes
- Configurable via `--timeout` flag

## Integration with Claude Code

### Slash Commands (Proposed)

Future Claude Code versions could support:
- `/monitor PR_NUMBER` - Start monitoring a PR
- `/monitor-stop` - Stop current monitoring
- `/monitor-status` - Check monitoring status

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
[Runs monitoring agent]
[Detects admin comment]
Claude: Admin posted: "[ADMIN] Please add tests"
[Implements tests and responds]
```

### Example 3: Conditional Response

```python
# The agent intelligently decides if response is needed
{
  "needs_response": false,  # CI results don't need response
  "response_type": "ci_results",
  "action_required": "Review CI results if failures present"
}
```

## Best Practices

1. **Use Write Tool for Responses**: Always create response files with Write tool to avoid escaping issues with reaction images
2. **Check Priority**: High priority (admin commands) should be addressed immediately
3. **Timeout Appropriately**: Set longer timeouts for complex reviews
4. **Monitor Specific PRs**: Always specify PR number to avoid confusion

## Troubleshooting

### Monitor Not Detecting Comments

1. Check GitHub CLI authentication: `gh auth status`
2. Verify PR exists: `gh pr view PR_NUMBER`
3. Check script permissions: `chmod +x scripts/pr-monitoring/*`

### Escaping Issues in Responses

Always use file-based responses:
```bash
# Good - Use Write tool
Write to /tmp/response.md
gh pr comment PR --body-file /tmp/response.md

# Bad - Direct body flag
gh pr comment PR --body "![Reaction](...)"  # Will escape !
```

### Timeout Issues

Increase timeout for long-running reviews:
```bash
monitor-pr 48 --timeout 3600  # 1 hour
```

## Implementation Details

### File Locations

```
scripts/pr-monitoring/
├── monitor.sh           # Core monitoring script
├── pr_monitor_agent.py  # Intelligent analyzer
└── monitor-pr          # User-friendly wrapper
```

### Required Dependencies

- GitHub CLI (`gh`)
- Python 3.6+
- Bash 4.0+
- jq (for JSON parsing in bash)

### Security Considerations

- Only responds to authorized users (admin, github-actions)
- No credentials stored in scripts
- Uses GitHub CLI authentication
- Timeouts prevent infinite loops

## Future Enhancements

1. **WebSocket Monitoring**: Real-time updates instead of polling
2. **Multiple PR Support**: Monitor several PRs simultaneously
3. **Custom Triggers**: Configure additional users/keywords
4. **Notification System**: Desktop/email alerts
5. **Claude Code Integration**: Native slash commands
6. **Pattern Matching**: Regex-based response triggers
7. **Response Templates**: Predefined responses for common scenarios
