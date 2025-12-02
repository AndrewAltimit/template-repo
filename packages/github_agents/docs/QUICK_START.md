# Quick Start Guide

Get up and running with GitHub Agents in 5 minutes.

## Prerequisites

Before you begin, ensure you have:
- Python 3.11 or higher
- GitHub CLI (`gh`) installed
- A GitHub account with repository access
- Git installed

## 5-Minute Setup

### Step 1: Installation (1 minute)

Clone the repository and install the package:

```bash
# Clone repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Install package in editable mode
pip install -e packages/github_agents
```

### Step 2: Configure GitHub Access (1 minute)

Set up your GitHub credentials:

```bash
# Set GitHub token (create at https://github.com/settings/tokens)
export GITHUB_TOKEN=your_github_token_here

# Set your repository
export GITHUB_REPOSITORY=owner/repo
```

**Token Permissions Required:**
- `repo` - Full control of private repositories
- `write:discussion` - Read and write discussions (optional)

###Step 3: Configure Agent API Keys (1 minute)

Choose at least one AI agent and configure its API key:

**Option A: OpenCode/Crush (Recommended for Getting Started)**
```bash
export OPENROUTER_API_KEY=your_openrouter_key_here
```

Get your key at: https://openrouter.ai/keys

**Option B: Claude (Requires Subscription)**
```bash
# Install Claude CLI
npm install -g @anthropic-ai/claude-code

# Authenticate (requires Claude Pro subscription)
claude-code auth
```

**Option C: Gemini (Optional)**
```bash
export GEMINI_API_KEY=your_gemini_key_here
```

### Step 4: Run Issue Monitor (1 minute)

Start the issue monitor to watch for trigger comments:

```bash
issue-monitor
```

You should see output like:
```
[INFO] GitHub Agents - Issue Monitor
[INFO] Watching repository: owner/repo
[INFO] Checking for new issues...
[INFO] No new issues with trigger keywords found.
```

### Step 5: Test with Sample Issue (1 minute)

Create a test issue to verify the setup:

```bash
# Create test issue with trigger keyword
gh issue create \
  --title "Test: Hello World Function" \
  --body "Please implement a hello world function in Python.

[Approved][OpenCode]"
```

The issue monitor will:
1. Detect the `[Approved][OpenCode]` trigger
2. Generate Python code for the hello world function
3. Create a pull request with the implementation

**Verify it worked:**
```bash
# Check for new PRs
gh pr list

# You should see a PR created by the agent
```

## What Just Happened?

1. Issue monitor detected your issue with `[Approved][OpenCode]` trigger
2. OpenCode agent generated code based on the issue description
3. A new branch was created with the generated code
4. A pull request was automatically created and linked to the issue

## Next Steps

### Monitor Pull Requests

Watch for review comments on PRs and implement fixes automatically:

```bash
pr-monitor --pr-number 123
```

### Continuous Monitoring

Run monitors continuously (recommended for production):

```bash
# Issue monitor (checks every 5 minutes)
issue-monitor --continuous --interval 300

# PR monitor for specific PR
pr-monitor --pr-number 123 --continuous
```

### Use Different Agents

Try other agents by changing the trigger keyword:

```markdown
[Approved][Claude]   # Use Claude for comprehensive code generation
[Approved][Gemini]   # Use Gemini for code review
[Approved][Crush]    # Use Crush for fast code generation
```

### Configure Security

Add your GitHub username to the allow list:

```bash
# Edit .github/ai-agents-security.yml
allowed_users:
  - your-github-username
```

See [Security Documentation](security.md) for complete setup.

### Run in GitHub Actions

Set up automated monitoring with GitHub Actions:

```yaml
# .github/workflows/ai-agents.yml
name: Agents

on:
  schedule:
    - cron: '0 * * * *'  # Every hour
  workflow_dispatch:

jobs:
  issue-monitor:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v6
      - name: Install package
        run: pip install -e packages/github_agents
      - name: Run monitor
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: issue-monitor
```

## Troubleshooting

### Issue Monitor Not Finding Issues

**Problem:** Monitor runs but doesn't detect issues

**Check:**
1. Issue has the correct trigger format: `[Approved][AgentName]`
2. Agent name is capitalized correctly
3. Your GitHub username is in the allow list
4. The issue is open (not closed)

### Agent Not Available

**Problem:** Error message says agent is not available

**Check:**
1. API key is set correctly: `echo $OPENROUTER_API_KEY`
2. API key has sufficient credits/quota
3. Network connection is working

### Permission Denied

**Problem:** Cannot create PR or push commits

**Check:**
1. GitHub token has `repo` scope
2. You have write access to the repository
3. Token is not expired

### Rate Limiting

**Problem:** GitHub API rate limit exceeded

**Solution:**
- Increase monitoring interval: `--interval 600` (10 minutes)
- Use GitHub Actions built-in `GITHUB_TOKEN` (higher limits)
- Check rate limit status: `gh api rate_limit`

## Learning More

Now that you're up and running:

1. **Read the Full Installation Guide:** [INSTALLATION.md](INSTALLATION.md)
2. **Explore Security Features:** [security.md](security.md)
3. **Learn About Subagents:** [subagents.md](subagents.md)
4. **Review Examples:** `examples/` directory *(coming in v0.2.0)*
5. **Check the Documentation Index:** [INDEX.md](INDEX.md)

## Getting Help

- **Documentation:** [INDEX.md](INDEX.md)
- **Issues:** [GitHub Issues](https://github.com/AndrewAltimit/template-repo/issues)
- **Tests:** See `tests/` directory for working examples

---

**Congratulations!** You've successfully set up GitHub Agents. Start by creating issues with trigger keywords and watch the agents work their magic.
