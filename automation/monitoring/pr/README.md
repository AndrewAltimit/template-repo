# PR Monitoring Scripts

Quick-start scripts for monitoring GitHub Pull Requests for new comments.

## Quick Usage

```bash
# Basic monitoring
./automation/monitoring/pr/monitor-pr.sh 48

# With custom timeout (30 minutes)
./automation/monitoring/pr/monitor-pr.sh 48 --timeout 1800

# JSON output only (for automation)
./automation/monitoring/pr/monitor-pr.sh 48 --json

# Monitor comments after a specific commit
./automation/monitoring/pr/monitor-pr.sh 48 --since-commit abc1234
```

## Files

- **monitor.sh** - Core bash monitoring script
- **pr_monitor_agent.py** - Intelligent Python agent for comment analysis
- **monitor-pr.sh** - User-friendly wrapper script

## How It Works

1. Monitors specified PR for new comments
2. Detects comments from admin (AndrewAltimit) or AI reviewers
3. Returns structured JSON data for Claude to process
4. Exits when relevant comment is found or timeout reached

## Full Documentation

See [/docs/ai-agents/pr-monitoring.md](/docs/ai-agents/pr-monitoring.md) for complete documentation.

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
