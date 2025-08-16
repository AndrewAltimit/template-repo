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
     python automation/monitoring/pr/pr_monitor_agent.py 54 --since-commit abc1234

  🔄 Or monitor all new comments:
     python automation/monitoring/pr/pr_monitor_agent.py 54

This will watch for:
  • Admin comments and commands
  • Gemini AI code review feedback
  • CI/CD validation results

💡 The monitor will return structured data when relevant comments are detected.
============================================================
```

### Dependencies

For optimal functionality, install these tools:

```bash
# GitHub CLI (required for PR detection)
# Ubuntu/Debian:
sudo apt install gh
# Or download from: https://cli.github.com/

# jq (recommended for robust JSON parsing)
# Ubuntu/Debian:
sudo apt install jq
# macOS:
brew install jq
```

### Installation

#### Automatic Installation

To install the pre-push hook in your local repository:

```bash
# Copy the pre-push hook to your git hooks directory
cp scripts/git-hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

#### Manual Installation

If you prefer to install manually or need to combine with existing hooks:

1. Create or edit `.git/hooks/pre-push`
2. Add the monitoring reminder functionality (see `scripts/git-hooks/pre-push` for reference)
3. Make the hook executable: `chmod +x .git/hooks/pre-push`

#### Important Notes

- This is a local git hook that is NOT tracked in the repository (stays local to your clone)
- If you have Git LFS installed, the hook will automatically combine with LFS functionality
- Requires `gh` CLI to be installed for PR detection to work
- Recommends `jq` for robust JSON parsing (falls back to grep if not available)

### Customization

To modify or disable the hook, edit `.git/hooks/pre-push` in your local repository.

### Related Tools

- **PR Monitor Agent**: `automation/monitoring/pr/pr_monitor_agent.py`
- **Universal Security Hooks**: See `automation/security/README.md`
- **GitHub AI Agents**: Automated PR and issue monitoring

## Security Hooks (Universal)

The repository includes universal security hooks that work with ALL agents through shell aliasing:

- **Universal Wrapper**: `automation/security/gh-wrapper.sh`
  - Masks secrets in GitHub comments
  - Validates command safety
  - Works for all agents including Claude Code
  - Setup via: `source automation/security/setup-agent-hooks.sh`

These hooks ensure that sensitive information is never accidentally posted to GitHub through any automation tool or manual operation.
