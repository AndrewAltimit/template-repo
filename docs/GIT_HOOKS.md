# Git Hooks Documentation

## PR Monitoring Reminder (pre-push hook)

This repository includes a git pre-push hook that automatically reminds developers to monitor PRs for feedback after pushing commits.

### Features

- **Automatic PR Detection**: Detects if the current branch has an open PR
- **Monitoring Instructions**: Provides exact commands to monitor PR feedback
- **Works Everywhere**: Functions with all git push operations (CLI, Claude Code, AI agents, etc.)
- **Git LFS Compatible**: Preserves existing Git LFS functionality

### What It Does

When you run `git push`, the hook will:

1. Check if your branch has an open PR
2. Display monitoring instructions with the correct PR number and commit SHA
3. Remind you about the types of feedback to watch for (admin comments, Gemini reviews, CI/CD)

### Example Output

```
============================================================
🔄 PR FEEDBACK MONITORING REMINDER
============================================================

You're pushing commits to PR #54 on branch 'refine'.
After push completes, consider monitoring for feedback:

  📍 Monitor from this commit onwards:
     python scripts/pr-monitoring/pr_monitor_agent.py 54 --since-commit abc1234

  🔄 Or monitor all new comments:
     python scripts/pr-monitoring/pr_monitor_agent.py 54

This will watch for:
  • Admin comments and commands
  • Gemini AI code review feedback
  • CI/CD validation results

💡 The monitor will return structured data when relevant comments are detected.
============================================================
```

### Installation

The hook is already installed in `.git/hooks/pre-push`. It's a local git hook that:
- Is NOT tracked in the repository (stays local to your clone)
- Combines with existing Git LFS functionality
- Requires `gh` CLI to be installed for PR detection

### Customization

To modify or disable the hook, edit `.git/hooks/pre-push` in your local repository.

### Related Tools

- **PR Monitor Agent**: `scripts/pr-monitoring/pr_monitor_agent.py`
- **Claude Code Hooks**: Security hooks in `.claude/settings.json`
- **GitHub AI Agents**: Automated PR and issue monitoring

## Security Hooks (Claude Code)

The repository also includes Claude Code security hooks configured in `.claude/settings.json`:

- **PreToolUse Bash Hook**: `scripts/security-hooks/bash-pretooluse-hook.sh`
  - Masks secrets in GitHub comments
  - Validates command safety
  - Configured for all Bash commands in Claude Code

These hooks ensure that sensitive information is never accidentally posted to GitHub through automation tools.
