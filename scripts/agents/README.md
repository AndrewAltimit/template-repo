# AI Agents Security Documentation

## Overview

The AI agents system includes comprehensive security measures to prevent unauthorized use and protect against prompt injection attacks. Only users on an explicit allow list can trigger AI agent actions using specific keyword triggers.

## Security Features

### 1. Multi-Layer Security Implementation

Our AI agents implement defense-in-depth with multiple security layers:

#### Workflow-Level Security (First Layer)
- **GitHub Actions `if` conditions** prevent workflows from running for unauthorized users
- **Fail-fast security checks** terminate workflows immediately for unauthorized access
- **Minimal GITHUB_TOKEN permissions** following principle of least privilege

#### Application-Level Security (Second Layer)
- **Allow List Based Authorization**: Only specific GitHub usernames can trigger agent actions
- **Rate Limiting**: Prevents abuse with configurable request limits per user
- **Repository Validation**: Restricts agents to specific repositories
- **Comprehensive Security Checks**: All layers validated before any action

### 2. Default Allow List

The allow list is configured in `config.json` under the `security.allow_list` field. The repository owner (extracted from `GITHUB_REPOSITORY` environment variable) is always included automatically.

### 3. Keyword Trigger System

To prevent accidental or unauthorized agent activation, AI agents require specific keyword triggers in comments from allowed users:

#### Trigger Format
The trigger format is: `[Action][Agent]`

#### Supported Actions
- `[Approved]` - Approve and process the issue/PR
- `[Fix]` - Fix the reported issue
- `[Implement]` - Implement the requested feature
- `[Review]` - Review and address feedback
- `[Close]` - Close the issue/PR
- `[Summarize]` - Provide a summary
- `[Debug]` - Debug the issue

#### Supported Agents
- `[Claude]` - Claude Code agent
- `[Gemini]` - Gemini CLI agent

#### Examples
- `[Approved][Claude]` - Have Claude process the issue
- `[Fix][Claude]` - Have Claude fix the reported bug
- `[Summarize][Gemini]` - Have Gemini provide a summary
- `[Close][Claude]` - Have Claude close the issue
- `[Review][Gemini]` - Have Gemini review and address PR feedback

#### How It Works
1. An allowed user comments on an issue/PR with a keyword trigger
2. The agent checks for the most recent valid trigger from an allowed user
3. If found, the agent processes the request based on the action
4. The agent selection (`[Claude]`, `[Gemini]`, etc.) can be used for routing to specific agents

### 4. Configuration

Security settings are configured in `config.json`:

```json
{
  "security": {
    "enabled": true,
    "allow_list": [
      "AndrewAltimit",
      "github-actions[bot]",
      "gemini-bot",
      "ai-agent[bot]"
    ],
    "log_violations": true,
    "reject_message": "This AI agent only processes requests from authorized users to prevent security vulnerabilities. Please contact the repository owner if you believe you should have access.",
    "rate_limit_window_minutes": 60,
    "rate_limit_max_requests": 10,
    "allowed_repositories": []
  }
}
```

#### Configuration Options:
- `enabled`: Master switch for all security features
- `allow_list`: Array of allowed GitHub usernames
- `log_violations`: Whether to log security violations
- `reject_message`: Custom message shown to unauthorized users
- `rate_limit_window_minutes`: Time window for rate limiting (default: 60)
- `rate_limit_max_requests`: Maximum requests per window (default: 10)
- `allowed_repositories`: Array of allowed repositories (empty = all repos from owner)

### 4. Environment Variables

You can also set the allow list via environment variable:
```bash
export AI_AGENT_ALLOW_LIST="user1,user2,bot-name[bot]"
```

### 5. Security Manager API

The `SecurityManager` class provides comprehensive security methods:

```python
from security import SecurityManager

# Initialize security manager
security = SecurityManager()

# Basic checks
is_allowed = security.is_user_allowed("username")
is_allowed = security.check_issue_security(issue_dict)
is_allowed = security.check_pr_security(pr_dict)

# Enhanced security check with all layers
is_allowed, reason = security.perform_full_security_check(
    username="user",
    action="issue_process",
    repository="owner/repo",
    entity_type="issue",
    entity_id="123"
)

# Rate limiting check
is_allowed, reason = security.check_rate_limit("username", "action")

# Repository validation
is_allowed = security.check_repository("owner/repo")

# Log security violations
security.log_security_violation("issue", "123", "attacker")

# Keyword trigger parsing
trigger = security.parse_keyword_trigger("[Approved][Claude]")
# Returns: ("Approved", "Claude") or None

# Check for keyword triggers in issue/PR
trigger_info = security.check_trigger_comment(issue_dict, "issue")
# Returns: (action, agent, username) or None
```

### 6. Security Violation Handling

When an unauthorized user attempts to trigger AI agents:

1. **Workflow Level**: GitHub Action terminates immediately with security error
2. **Application Level**: Additional checks for defense-in-depth:
   - User authorization check
   - Repository validation
   - Rate limit enforcement
3. **Logging**: Detailed security violation logged with context
4. **User Feedback**: Comment posted with specific rejection reason:
   - Unauthorized user
   - Rate limit exceeded
   - Repository not allowed
5. **Audit Trail**: All violations tracked for security monitoring

### 7. Disabling Security

⚠️ **WARNING**: Disabling security allows ALL users to trigger AI agents, which can lead to:
- Prompt injection attacks
- Resource abuse
- Unauthorized code changes
- Potential security vulnerabilities

To disable security (NOT RECOMMENDED):
```json
{
  "security": {
    "enabled": false
  }
}
```

### 8. Testing Security

Run the security test suite:
```bash
cd scripts/agents
python3 test_security.py
```

This verifies:
- Allow list functionality
- Issue/PR security checks
- Security violation logging
- Configuration loading
- Behavior when security is disabled

## Best Practices

1. **Keep Allow List Minimal**: Only add trusted users and bots
2. **Review Regularly**: Periodically audit the allow list
3. **Monitor Logs**: Check for security violations in agent logs
4. **Never Disable**: Keep security enabled in production
5. **Use Bot Accounts**: Create dedicated bot accounts for automation

## Security Architecture

### Gemini's Security Recommendations Implemented

Based on consultation with Gemini AI, we've implemented:

1. **Workflow-Level Authorization** (Critical)
   - GitHub Actions `if` conditions check users before Python scripts run
   - Fail-fast approach prevents any code execution for unauthorized users
   - This addresses Gemini's concern about relying solely on application-level checks

2. **Minimal Token Permissions** (Critical)
   - `contents: read` instead of `write` where possible
   - Explicit permission declarations
   - Following principle of least privilege

3. **Rate Limiting** (Important)
   - Prevents abuse even from authorized users
   - Configurable per-action limits
   - Protects against compromised accounts

4. **Repository Validation** (Important)
   - Restricts agents to specific repositories
   - Prevents lateral movement if account compromised

### Remaining Considerations

Per Gemini's analysis, these risks still require external mitigation:

1. **Account Compromise**: Enable 2FA on all allowed GitHub accounts
2. **Token Security**: Secure storage of GITHUB_TOKEN and API keys
3. **Workflow File Security**: Restrict write access to `.github/workflows/`

## AI Agent Controls

The `ENABLE_AI_AGENTS` environment variable is a master switch that controls:

1. **Scheduled Runs**: When `false`, cron-triggered workflows won't run
2. **Auto-Fix Capability**: When `true`, PR Review Monitor can implement code fixes
3. **Manual Triggers**: Still work regardless of this setting for testing

### Auto-Fix Security Features:

1. **Disabled by Default**: Requires `ENABLE_AI_AGENTS=true` in GitHub Environment
2. **Limited Scope**: Will not auto-fix if more than 20 issues are found
3. **Backup Creation**: Creates a backup branch before making any changes
4. **Timeout Protection**: Auto-fix operations timeout after 5 minutes
5. **Sandboxed Execution**: Runs in a separate shell script with error checking

To enable AI agents (including auto-fix):
```bash
# For local testing
export ENABLE_AI_AGENTS=true
./scripts/agents/run_agents.sh pr-review

# For production
# Set ENABLE_AI_AGENTS=true in GitHub Environment Variables
```

**Security Recommendation**: Only enable in controlled environments with trusted reviewers.
4. **Code Review**: All changes to workflows and agent scripts must be reviewed

## Security Considerations

This security implementation protects against:
- **Prompt Injection**: Multiple layers prevent malicious command injection
- **Impersonation**: Workflow-level checks prevent spoofed requests
- **Resource Abuse**: Rate limiting prevents excessive AI usage
- **Unauthorized Changes**: Only trusted users can trigger code changes
- **Social Engineering**: Multi-layer validation prevents bypass attempts

## Adding New Users

To add a new trusted user:

1. Edit `config.json` and add username to `allow_list`
2. Or set `AI_AGENT_ALLOW_LIST` environment variable
3. Restart the agents for changes to take effect

## Monitoring

Security violations are logged with:
- Timestamp
- Entity type (issue/PR)
- Entity ID
- Username of violator
- Warning level logging

Example log entry:
```
2025-07-23 09:00:00 - security - WARNING - SECURITY VIOLATION: Unauthorized issue #123 from user 'attacker'. AI agent will not process this issue to prevent potential prompt injection.
```

## GitHub Token Permissions

The AI agents require a fine-grained Personal Access Token with exactly these permissions:

| Permission | Access Level | Why It's Needed |
|------------|--------------|-----------------|
| **Actions** | Read | View workflow runs and logs |
| **Commit statuses** | Read | Check CI/CD status on PRs |
| **Contents** | Read + Write | Clone repo, create branches, push commits |
| **Issues** | Read + Write | Read issues, post comments |
| **Pull requests** | Read + Write | Read PRs, create PRs, post comments |

**Important**: Do NOT grant any Account permissions - only Repository permissions are needed.

See [GitHub Environments Setup Guide](../../docs/GITHUB_ENVIRONMENTS_SETUP.md) for detailed token creation instructions.

## Enhanced Security Features (v2)

Recent security improvements include:

### 1. GitHub Environments Support

The agents use GitHub Environments for secure secret management:

- Secrets are managed in GitHub, never stored in files
- Environment protection rules can require approvals
- Full audit trail of secret access

**Token Priority Order:**
1. `GITHUB_TOKEN` environment variable (standard for GitHub Actions)
2. Docker secret at `/run/secrets/github_token` (optional, for advanced setups)
3. GitHub CLI token via `gh auth token` (for local development)

### 2. Secret Redaction in Logs

All logging now includes automatic secret redaction to prevent accidental exposure:

- GitHub tokens (classic and fine-grained formats)
- API keys and passwords
- Bearer tokens and authorization headers
- URLs with embedded credentials

Example:
```
# Original: "Using token ghp_1234567890abcdef..."
# Logged as: "Using token [REDACTED]..."
```

### 3. Improved Rate Limiting

Rate limiting now features:

- **Atomic File Operations**: Prevents corruption during concurrent access
- **Persistent Storage**: Uses `~/.ai-agent-state/` for better container support
- **Retry Logic**: Handles file lock contention gracefully
- **Non-blocking Locks**: Uses `LOCK_NB` flag to prevent deadlocks

### 4. Repository Allowlist

The `allowed_repositories` configuration now explicitly defines which repositories agents can operate on:

```json
{
  "security": {
    "allowed_repositories": [
      "AndrewAltimit/template-repo"
    ]
  }
}
```

Empty list defaults to allowing all repositories from the repository owner.

### 5. Configuration Robustness

- All config loading now handles JSON decode errors gracefully
- Fallback to defaults if config is corrupted
- Warning logs for config issues without crashing

## Best Practices

1. **Use GitHub Environments**: Configure production environment with appropriate secrets
2. **Enable Protection Rules**: Require approvals for production deployments
3. **Monitor Logs**: Check for security violations and rate limit warnings
4. **Regular Updates**: Keep allow lists and repository lists current
5. **Minimal Permissions**: Use fine-grained PATs with minimal required permissions
6. **Test Locally**: Use gh CLI auth for local development
7. **Rotate Tokens**: Set expiration dates and rotate tokens regularly
