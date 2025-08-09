# PR Monitoring Scripts

Quick-start scripts for monitoring GitHub Pull Requests for new comments.

## Quick Usage

```bash
# Monitor PR #48
./monitor-pr 48

# Monitor with 30-minute timeout
./monitor-pr 48 --timeout 1800
```

## Files

- **monitor.sh** - Core bash monitoring script
- **pr_monitor_agent.py** - Intelligent Python agent for comment analysis
- **monitor-pr** - User-friendly wrapper script

## How It Works

1. Monitors specified PR for new comments
2. Detects comments from admin (AndrewAltimit) or AI reviewers
3. Returns structured JSON data for Claude to process
4. Exits when relevant comment is found or timeout reached

## Full Documentation

See [/docs/PR_MONITORING.md](/docs/PR_MONITORING.md) for complete documentation.

## Example Output

```json
{
  "needs_response": true,
  "priority": "high",
  "response_type": "admin_command",
  "action_required": "Execute admin command and respond",
  "comment": {
    "author": "AndrewAltimit",
    "timestamp": "2025-08-09T14:59:45Z",
    "body": "[ADMIN] Please add tests for this feature"
  }
}
```
