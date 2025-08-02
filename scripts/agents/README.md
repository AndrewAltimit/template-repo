# AI Agents Security Documentation

## Overview

The AI agents system implements a comprehensive security model designed to prevent unauthorized use, prompt injection attacks, and malicious code insertion. The system uses multiple layers of defense including user authentication, keyword-based command triggers, and real-time commit validation during PR processing.

## Core Security Principles

1. **Zero Trust by Default**: No action is taken without explicit authorization
2. **Defense in Depth**: Multiple security layers that work independently
3. **Audit Trail**: All actions are logged with user attribution
4. **Fail Secure**: Any security failure results in no action taken
5. **Real-time Validation**: Continuous security checks during execution

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

### 3. Keyword Trigger System - Command and Control

AI agents are controlled exclusively through a keyword trigger system that requires explicit commands from authorized users. This prevents accidental activation and provides clear audit trails.

#### Trigger Format
The trigger format is: `[Action][Agent]`

**Security Properties:**
- Case-insensitive matching for user convenience
- Must be exact format with square brackets
- Only the most recent trigger is processed
- Invalid triggers are ignored (fail secure)

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
- `[Approved][Claude]` - Have Claude process the issue/PR
- `[Fix][Claude]` - Have Claude fix the reported bug
- `[Implement][Claude]` - Have Claude implement a feature
- `[Review][Claude]` - Have Claude review and address PR feedback
- `[Close][Claude]` - Have Claude close the issue
- `[Summarize][Gemini]` - Have Gemini provide a summary
- `[Debug][Claude]` - Have Claude debug an issue

#### Security Flow
1. **User Action**: An allowed user comments with `[Action][Agent]`
2. **Authentication**: System verifies user is in allow list
3. **Authorization**: System checks rate limits and repository permissions
4. **Validation**: System ensures trigger is on latest commit (for PRs)
5. **Execution**: Agent performs requested action
6. **Audit**: All actions logged with full context

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

### Kill Switch Functionality

The `ENABLE_AI_AGENTS` environment variable serves as a master kill switch:

1. **Scheduled Runs**: When `false`, cron-triggered workflows won't run
2. **Workflow Gating**: GitHub Actions check this variable before running
3. **Manual Override**: Manual workflow triggers bypass this for testing

**Emergency Shutdown Procedure:**

#### Step 1: set ENABLE_AI_AGENTS to false

Toggle via GitHub UI:
Settings → Variables → ENABLE_AI_AGENTS → Update → false

Toggle via GitHub CLI:

```bash
gh variable set ENABLE_AI_AGENTS --body="false"
```

#### Step 2: Disable AI agent itegrated workflows (e.g. issue/pr monitoring)

Actions → AI Agent Workflow → Disable Workflow

### Environment Isolation

**Critical Security Principle**: AI agents must be restricted to development environments only.

```yaml
# Example workflow configuration
jobs:
  ai-agent:
    environment: development  # NEVER use 'production' here
    env:
      GITHUB_TOKEN: ${{ secrets.AI_AGENT_TOKEN }}  # Limited scope token
```

**Environment Setup:**
- **Production**: No AI agent secrets or access
- **Staging**: No AI agent secrets or access
- **Development**: Limited AI agent token with minimal permissions

This ensures that even if all other security controls fail, AI agents cannot access production systems or secrets.

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

### PR Review Monitor Configuration

The PR Review Monitor relies on keyword triggers from authorized users for security:

1. **Keyword Triggers Required**: PRs are only processed when an authorized user comments with `[Action][Agent]`
   - No label requirements - keyword approval is sufficient
   - This simplifies the workflow and reduces configuration overhead
   - All security is handled through the allow list and keyword system

2. **Simplified Configuration**:
   - No label requirements or configurations needed
   - PRs are processed based solely on keyword triggers
   - Reduces configuration complexity and maintenance

3. **Configuration Examples**:
   ```json
   {
     "agents": {
       "issue_monitor": {
         "min_description_length": 50,
         "cutoff_hours": 24
       },
       "pr_review_monitor": {
         "cutoff_hours": 24,
         "auto_fix_threshold": {
           "critical_issues": 0,
           "total_issues": 5
         }
       }
     }
   }
   ```

4. **Code Review**: All changes to workflows and agent scripts must be reviewed

### 5. Developer Override Risk

**Known Limitation**: Developers with repository write access can modify `.github/workflows` files to potentially bypass security controls.

**Accepted Risk with Mitigations**:
1. **Environment Isolation**: Even if workflows are modified, agents only have DEV access
2. **Branch Protection**: Require reviews for `.github/workflows/**` changes
3. **Audit Trail**: All workflow modifications are tracked in git history
4. **Monitoring**: Regular reviews of workflow changes
5. **Token Scoping**: AI_AGENT_TOKEN has minimal permissions

**Recommended Branch Protection**:
```yaml
# .github/CODEOWNERS
.github/workflows/ @repository-owner @security-team

# Branch protection rules
- Require pull request reviews before merging
- Dismiss stale pull request approvals
- Require review from CODEOWNERS
```

### 4. Advanced Security: Commit-Level Validation for Pull Requests

The PR monitoring system implements sophisticated commit-level security to prevent code injection attacks during the review and modification process.

#### The Threat Model
Without commit validation, an attacker could:
1. Create an innocent-looking PR
2. Wait for approval from an authorized user
3. Push malicious code after approval but before AI processing
4. Have the AI agent unknowingly work on and push malicious code

#### Our Multi-Stage Defense

**Stage 1 - Approval Commit Tracking**
- When `[Approved][Claude]` is issued, the system records the exact commit SHA
- This creates an immutable "point-in-time" snapshot of what was approved
- The approval is cryptographically tied to the repository state

**Stage 2 - Pre-Execution Validation**
```
if (current_commit != approval_commit) {
    reject_with_security_notice();
    request_fresh_approval();
}
```
- Prevents any work if the PR has changed since approval
- Immediate failure with clear security message

**Stage 3 - Pre-Push Validation**
```bash
# Before pushing any changes
git fetch origin
if [ commits_since_approval > 0 ]; then
    abort_all_work();
    post_security_warning();
    exit 1;
fi
```
- Final check before any code enters the repository
- Drops all work if PR was modified during processing
- Prevents race conditions and TOCTOU attacks

#### Real-World Attack Prevention

**Scenario 1: Post-Approval Injection**
```
Time 0: Attacker creates PR with innocent code
Time 1: Admin reviews and approves with [Approved][Claude]
Time 2: Attacker pushes malicious commit
Time 3: AI agent detects mismatch and refuses to proceed ✓
```

**Scenario 2: Race Condition During Work**
```
Time 0: Admin approves PR with [Approved][Claude]
Time 1: AI agent begins working
Time 2: Attacker pushes malicious commit
Time 3: AI agent attempts to push
Time 4: Pre-push validation detects new commit and aborts ✓
```

#### Security Properties
- **Immutable Approval**: Approvals cannot be transferred to different code
- **Atomic Operations**: Either all changes are safe or nothing is pushed
- **Clear Attribution**: Every commit linked to specific approval
- **No Silent Failures**: All rejections create visible security notices

### 5. Implementation Security for Issues

The Issue Monitor Agent now implements complete solutions before creating PRs:

**Security Measures:**
- AI agent must successfully implement and commit code
- No placeholder or draft PRs allowed
- Failed implementations abort the entire process
- PRs are created only with working, tested code
- Clear error messages if implementation fails

**Benefits:**
- No half-completed PRs that could be exploited
- All PRs are ready for immediate review
- Reduces window for malicious interference
- Clear success/failure states

## Deterministic Security Processes

The AI agents implement three core deterministic security processes that ensure predictable and secure behavior:

### 1. Secret Masking for Agent Outputs

All agent outputs are processed through multi-layer secret masking before being posted to GitHub:

**Implementation:**
- **Logging**: `SecretRedactionFilter` automatically redacts secrets in all Python logs
- **GitHub Comments**: `mask_secrets()` method sanitizes all PR/issue comments
- **Error Details**: Command outputs from failed operations are masked
- **Pattern Detection**: Automatic detection of tokens, API keys, and credentials

**Example:**
```python
# In pr_review_monitor.py
masked_output = self.mask_secrets(agent_output)
masked_error_details = self.mask_secrets(error_details)
```

### 2. Deterministic Issue/PR Filtering

Issues and PRs are filtered through a strict, deterministic pipeline:

```
Time Filter → Trigger Check → Security Check → Rate Limit → Deduplication → Process
```

**Each stage is deterministic:**
- **Time**: Only items updated within `cutoff_hours` (default: 24h)
- **Trigger**: Must have exact `[Action][Agent]` format
- **Security**: User must be in `allow_list`
- **Rate Limit**: Enforced per user per time window
- **Deduplication**: Skip if `[AI Agent]` comment exists

### 3. Commit Validation Security

Prevents code injection by validating commits at three stages:

1. **Approval Recording**: SHA captured when `[Approved][Claude]` is issued
2. **Pre-Work Check**: Validates no new commits before starting
3. **Pre-Push Check**: Final validation before pushing changes

**Implementation in bash scripts:**
```bash
# Security check before push
if [ -n "$APPROVAL_COMMIT_SHA" ]; then
    NEW_COMMITS=$(git rev-list "$APPROVAL_COMMIT_SHA"..HEAD --count)
    if [ "$NEW_COMMITS" -gt 0 ]; then
        echo "ERROR: New commits detected!"
        exit 1
    fi
fi
```

For complete details on these deterministic processes, see [SECURITY.md](../../SECURITY.md).

## Complete Security Model Summary

### Attack Vectors Prevented

1. **Unauthorized Access**
   - ✓ Allow list prevents unauthorized users
   - ✓ Workflow-level checks block at GitHub Actions layer
   - ✓ Application-level validation as backup

2. **Prompt Injection**
   - ✓ Keyword triggers only accept predefined commands
   - ✓ No free-form text execution
   - ✓ Commands tied to specific users

3. **Code Injection**
   - ✓ Commit-level validation prevents post-approval attacks
   - ✓ Real-time validation during execution
   - ✓ Atomic operations ensure consistency

4. **Resource Abuse**
   - ✓ Rate limiting per user
   - ✓ Repository restrictions
   - ✓ Action-specific limits

5. **Social Engineering**
   - ✓ Multi-layer validation
   - ✓ Clear audit trails
   - ✓ Visible security notices

### Security Configuration

All security settings in `config.json`:
```json
{
  "security": {
    "enabled": true,
    "allow_list": ["trusted-user1", "trusted-user2"],
    "rate_limit_window_minutes": 60,
    "rate_limit_max_requests": 10,
    "allowed_repositories": ["owner/repo"],
    "log_violations": true,
    "reject_message": "Custom security message"
  }
}
```

### Security Best Practices

1. **Minimal Allow List**: Only add users who absolutely need access
2. **Regular Audits**: Review allow list quarterly
3. **Monitor Logs**: Check for security violations
4. **Test Security**: Regularly test with unauthorized users
5. **Update Promptly**: Keep security measures current
6. **Document Changes**: Track all security modifications

## Security Incident Response

If a security incident occurs:

1. **Immediate**: Disable AI agents via environment variable
2. **Investigate**: Check logs for unauthorized attempts
3. **Remediate**: Remove compromised users from allow list
4. **Document**: Record incident details
5. **Improve**: Update security measures based on findings

## Deduplication and State Management

The AI agents use a sophisticated deduplication system to prevent duplicate processing and ensure each issue/PR is only handled once per trigger.

### How Deduplication Works

#### 1. Comment-Based State Tracking
The agents use GitHub comments as a **stateless database** to track their work:
- Every agent action results in a comment with the `[AI Agent]` tag
- These comments serve as persistent "claims" on issues/PRs
- Before processing, agents check for existing claims

#### 2. Deduplication Flow
```
New Issue/PR Event
    ↓
Time Filter (last 24 hours) ← Deterministic pre-filter
    ↓
Has [Action][Agent] trigger? ← Only process explicit requests
    ↓
Security checks passed?
    ↓
Has [AI Agent] comment? ← THE KEY CHECK
    ↓
No? → Process & Post Comment (stake claim)
Yes? → Skip (already claimed)
```

#### 3. Implementation Details

**Issue Monitor (`issue_monitor.py`):**
- Uses `has_agent_comment()` to check for ANY comment containing `[AI Agent]`
- If found, skips processing entirely
- Simple but effective for preventing duplicate issue processing

**PR Review Monitor (`pr_review_monitor.py`):**
- Uses `has_agent_addressed_review()` to check for `[AI Agent]` + "addressed"
- More specific check - only skips if review was already addressed
- Allows for multiple different actions on the same PR

### Comment Patterns

Agents use specific comment patterns to mark their work:

**Issue Processing:**
- `[AI Agent] I've created a PR to address this issue...` - PR created
- `[AI Agent] I need more information...` - Info requested
- `[AI Agent] Issue closed as requested...` - Issue closed

**PR Review Processing:**
- `[AI Agent] I've reviewed and addressed the feedback...` - Review addressed
- `[AI Agent] I've reviewed the PR feedback and found no changes are required...` - No action needed

### Deterministic Pre-Filters

The system uses multiple filters to minimize unnecessary processing:

#### 1. Time-Based Filter (`cutoff_hours`)
- Default: Only process issues/PRs from last 24 hours
- Prevents processing old issues on every scheduled run
- Configurable in `config.json` under `agents.<agent_name>.cutoff_hours`

#### 2. Keyword Trigger Filter
- Only processes items with valid `[Action][Agent]` triggers
- Ignores all other issues/PRs entirely
- Checks comments in reverse chronological order (most recent first)

#### 3. Security Filters
- User allowlist check
- Rate limiting
- Repository validation
- All applied BEFORE the deduplication check

### Example Processing Flow

```
1. Issue #123 created by user
2. User comments: "[Fix][Claude] Please help with this bug"
3. Issue Monitor runs (every hour)
4. Checks filters:
   - Created within 24 hours? ✓
   - Has keyword trigger? ✓
   - User allowed? ✓
   - Rate limit OK? ✓
5. Checks deduplication:
   - Any [AI Agent] comments? ✗ (No)
6. Processes issue:
   - Creates PR #124
   - Posts: "[AI Agent] I've created PR #124 to address this issue..."
7. Next run (1 hour later):
   - Gets to deduplication check
   - Any [AI Agent] comments? ✓ (Yes!)
   - SKIPS - Already processed
```

### Edge Cases and Limitations

#### Handled Cases:
1. **Multiple Triggers**: If user posts new trigger after agent comment, it's still skipped
2. **Partial Completion**: If agent fails mid-process but posted initial comment, won't retry (prevents infinite loops)
3. **Time Window**: Old issues (>24 hours) are ignored unless updated

#### Known Limitations:
1. **Comment Deletion**: If someone deletes the agent's comment, it will reprocess
2. **Force Reprocessing**: No built-in way to force reprocessing (must delete agent comment)
3. **Cross-Agent Coordination**: Each agent type only checks for generic `[AI Agent]` tag
4. **No Persistent State**: State is tied to GitHub comments, not a database

### Design Philosophy

The comment-based approach was chosen for several reasons:
- **Simplicity**: No external database or state files needed
- **Transparency**: All state is visible in the GitHub UI
- **Portability**: State travels with the issue/PR
- **Audit Trail**: Clear history of agent actions
- **Reliability**: Leverages GitHub's reliable comment storage

This is why agents post comments even for simple acknowledgments - it's not just communication, it's the deduplication mechanism!

### Configuration

Deduplication behavior can be tuned in `config.json`:

```json
{
  "agents": {
    "issue_monitor": {
      "cutoff_hours": 24,  // Time window for processing
      "agent_tag": "[AI Agent]"  // Tag used in comments
    },
    "pr_review_monitor": {
      "cutoff_hours": 24,
      "agent_tag": "[AI Agent]"
    }
  }
}
```

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

## Secret Masking in Public Comments

The PR monitoring agent includes comprehensive secret masking to prevent accidental exposure of sensitive information in public PR comments:

### How It Works

1. **Workflow Configuration**: Define which environment variables to mask in the workflow YAML:
   ```yaml
   env:
     MASK_ENV_VARS: "GITHUB_TOKEN,AI_AGENT_TOKEN,ANTHROPIC_API_KEY"
   ```

2. **Auto-Detection**: The agent automatically detects sensitive variables based on naming patterns:
   - Variables starting with: `SECRET_`, `TOKEN_`, `API_`, `KEY_`, `PASSWORD_`, `PRIVATE_`
   - Variables ending with: `_SECRET`, `_TOKEN`, `_API_KEY`, `_KEY`, `_PASSWORD`, `_PRIVATE_KEY`

3. **Pattern Matching**: Common secret patterns are always masked:
   - GitHub tokens: `ghp_*`, `ghs_*`, `github_pat_*`
   - API keys: `sk-*`, `pk-*`
   - Bearer tokens
   - URLs with embedded credentials

4. **Error Log Masking**: When pipeline fixes fail, error details are automatically masked before posting to PR comments

### Configuration

In your workflow files:
```yaml
- name: Run PR review monitor in container
  env:
    # Secrets to use
    GITHUB_TOKEN: ${{ secrets.AI_AGENT_TOKEN }}
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    # Which ones to mask in public comments
    MASK_ENV_VARS: "GITHUB_TOKEN,AI_AGENT_TOKEN,ANTHROPIC_API_KEY"
```

The agent will:
1. Read the `MASK_ENV_VARS` list
2. Auto-detect additional sensitive variables
3. Replace any occurrence of these values with `[VARIABLE_NAME]` in error logs
4. Apply pattern-based masking for common secret formats

### Important Notes

- GitHub Actions automatically masks registered secrets in workflow logs, but this doesn't apply to PR comments
- The masking happens before any text is posted as a PR comment
- Both stdout and stderr from failed commands are masked
- The masking is case-insensitive for patterns but exact-match for environment variable values

## Autonomous Mode for CI/CD

All AI agents are configured to run in **fully autonomous mode** for CI/CD environments. This is a critical requirement for automated workflows.

### Why Autonomous Mode?

In CI/CD environments (GitHub Actions, GitLab CI, etc.):
- No human interaction is possible (no TTY)
- Workflows must run unattended
- Interactive prompts would block pipelines indefinitely
- Agents run in sandboxed environments for security

### Key Configuration: `--dangerously-skip-permissions`

The Claude agent uses the `--dangerously-skip-permissions` flag, which might seem concerning but is:
- **Required** for CI/CD automation
- **Safe** when running in sandboxed environments
- **Necessary** to bypass interactive permission prompts

### Security Context

All agents run in isolated environments:
```yaml
# Example: GitHub Actions with Docker isolation
- name: Run AI Agent
  run: |
    docker run --rm \
      --memory="1g" \
      --cpus="1" \
      --read-only \
      --network="none" \
      -v ${{ github.workspace }}:/workspace:ro \
      ai-agents:latest
```

### Agent-Specific Flags

Each agent has specific flags for autonomous operation:
- **Claude**: `--print --dangerously-skip-permissions`
- **Gemini**: `-m model -p prompt` (non-interactive by design)
- **OpenCode**: `--non-interactive`
- **Codex**: `--non-interactive`
- **Crush**: `--non-interactive --no-update`

For detailed autonomous mode documentation, see [AUTONOMOUS_MODE.md](AUTONOMOUS_MODE.md).

## Best Practices

1. **Use GitHub Environments**: Configure production environment with appropriate secrets
2. **Enable Protection Rules**: Require approvals for production deployments
3. **Monitor Logs**: Check for security violations and rate limit warnings
4. **Regular Updates**: Keep allow lists and repository lists current
5. **Minimal Permissions**: Use fine-grained PATs with minimal required permissions
6. **Test Locally**: Use gh CLI auth for local development
7. **Rotate Tokens**: Set expiration dates and rotate tokens regularly
8. **Review Error Logs**: Always review error logs in PR comments to ensure no secrets leaked
9. **Follow GitHub Etiquette**: All agents must follow guidelines in [`docs/GITHUB_ETIQUETTE_FOR_AI_AGENTS.md`](../../docs/GITHUB_ETIQUETTE_FOR_AI_AGENTS.md)
   - Never use @ mentions for AI agent names (Gemini, Claude, etc.)
   - Only @ mention actual repository contributors
   - This prevents pinging unrelated GitHub users
