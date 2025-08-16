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
- `[OpenCode]` - Open-source coding AI
- `[Crush]` - Charm Bracelet Crush AI shell assistant

#### Examples
- `[Approved][Claude]` - Have Claude process the issue/PR
- `[Fix][OpenCode]` - Have OpenCode fix the reported bug
- `[Implement][Claude]` - Have Claude implement a feature
- `[Review][Gemini]` - Have Gemini review and address PR feedback

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

### 5. Environment Variables

You can also set the allow list via environment variable:
```bash
export AI_AGENT_ALLOW_LIST="user1,user2,bot-name[bot]"
```

### 6. Security Manager API

The `SecurityManager` class provides comprehensive security methods:

```python
from github_ai_agents.security import SecurityManager

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

## Advanced Security Features

### 1. Commit-Level Validation for Pull Requests

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
```python
if current_commit != approval_commit:
    reject_with_security_notice()
    request_fresh_approval()
```
- Prevents any work if the PR has changed since approval
- Immediate failure with clear security message

**Stage 3 - Pre-Push Validation**
```bash
# Before pushing any changes
git fetch origin
if [ commits_since_approval > 0 ]; then
    abort_all_work()
    post_security_warning()
    exit 1
fi
```
- Final check before any code enters the repository
- Drops all work if PR was modified during processing
- Prevents race conditions and TOCTOU attacks

### 2. Automatic Secret Masking via PreToolUse Hooks

The system implements real-time secret masking through PreToolUse hooks that intercept and sanitize all GitHub comments before they are posted. This is a **deterministic, automatic process** that ensures secrets can never appear in public comments.

#### Architecture

```
Agent Tool Call → PreToolUse Hook → Secret Masker → GitHub Comment
```

#### How It Works

1. **Central Configuration** (`.secrets.yaml`):
   ```yaml
   environment_variables:
     - GITHUB_TOKEN
     - OPENROUTER_API_KEY
     - DB_PASSWORD

   patterns:
     - name: GITHUB_TOKEN
       pattern: "ghp_[A-Za-z0-9_]{36,}"

   auto_detection:
     enabled: true
     include_patterns: ["*_TOKEN", "*_SECRET", "*_KEY"]
     exclude_patterns: ["PUBLIC_*"]
   ```

2. **Hook Integration** (`scripts/security-hooks/`):
   - `bash-pretooluse-hook.sh` - Entry point for all agents
   - `github-secrets-masker.py` - Universal secret masking engine
   - Works transparently - agents don't know masking occurred

3. **Auto-Detection**: The system automatically detects sensitive variables:
   - Variables matching patterns: `*_TOKEN`, `*_SECRET`, `*_KEY`, `*_PASSWORD`
   - Excludes safe patterns: `PUBLIC_*`, `*_ENABLED`

4. **Pattern Matching**: Common secret formats are detected and masked:
   - GitHub tokens: `ghp_*`, `ghs_*`, `github_pat_*`
   - API keys: `sk-*`, `pk-*`
   - JWT tokens: `eyJ*`
   - Bearer tokens
   - URLs with embedded credentials
   - Private key blocks

5. **Real-time Processing**:
   - Intercepts `gh pr comment`, `gh issue comment`, `gh pr create` commands
   - Extracts body content from `--body` flags
   - Replaces secrets with `[MASKED_VARNAME]` placeholders
   - Returns modified command for execution

#### Benefits

- **Universal**: Works with all AI agents and automation tools
- **Automatic**: No agent configuration required
- **Comprehensive**: Covers environment variables, patterns, and auto-detection
- **Transparent**: Agents are unaware of masking
- **Centralized**: Single configuration file for all secrets

### 3. Deduplication and State Management

The AI agents use a sophisticated deduplication system to prevent duplicate processing and ensure each issue/PR is only handled once per trigger.

#### How Deduplication Works

1. **Comment-Based State Tracking**
   - Every agent action results in a comment with the `[AI Agent]` tag
   - These comments serve as persistent "claims" on issues/PRs
   - Before processing, agents check for existing claims

2. **Deduplication Flow**
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

3. **Implementation Details**
   - Uses `has_agent_comment()` to check for ANY comment containing `[AI Agent]`
   - If found, skips processing entirely
   - Simple but effective for preventing duplicate processing

## Security Configuration Best Practices

1. **Keep Allow List Minimal**: Only add trusted users and bots
2. **Review Regularly**: Periodically audit the allow list
3. **Monitor Logs**: Check for security violations in agent logs
4. **Never Disable**: Keep security enabled in production
5. **Use Bot Accounts**: Create dedicated bot accounts for automation

## Security Incident Response

If a security incident occurs:

1. **Immediate**: Disable AI agents via environment variable
2. **Investigate**: Check logs for unauthorized attempts
3. **Remediate**: Remove compromised users from allow list
4. **Document**: Record incident details
5. **Improve**: Update security measures based on findings

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

## Autonomous Mode for CI/CD

All AI agents are configured to run in **fully autonomous mode** for CI/CD environments. This is a critical requirement for automated workflows.

### Why Autonomous Mode?

In CI/CD environments (GitHub Actions, GitLab CI, etc.):
- No human interaction is possible (no TTY)
- Workflows must run unattended
- Interactive prompts would block pipelines indefinitely
- Agents run in sandboxed environments for security

### Agent-Specific Flags

Each agent has specific flags for autonomous operation:
- **Claude**: `--print --dangerously-skip-permissions`
- **Gemini**: `-m model -p prompt` (non-interactive by design)
- **OpenCode**: `--non-interactive`
- **Crush**: `--non-interactive --no-update`

## GitHub Etiquette

All agents must follow these guidelines to prevent accidentally notifying random GitHub users:

- **NEVER use @ mentions** unless referring to actual repository maintainers
- Do NOT use @Gemini, @Claude, @OpenAI, etc. - these may ping unrelated GitHub users
- Instead, refer to AI agents without the @ symbol: "Gemini", "Claude", "OpenAI"
- Only @ mention users who are:
  - The repository owner
  - Active contributors listed in the repository
  - Users who have explicitly asked to be mentioned

When referencing AI reviews, use phrases like:
- "As noted in Gemini's review..."
- "Addressing Claude's feedback..."
- "Per the AI agent's suggestion..."
