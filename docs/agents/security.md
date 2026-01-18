# AI Agents Security Documentation

## Overview

The agents system implements a comprehensive security model designed to prevent unauthorized use, prompt injection attacks, and malicious code insertion. The system uses multiple layers of defense including user authentication, keyword-based command triggers, and real-time commit validation during PR processing.

## Core Security Principles

1. **Zero Trust by Default**: No action is taken without explicit authorization
2. **Defense in Depth**: Multiple security layers that work independently
3. **Audit Trail**: All actions are logged with user attribution
4. **Fail Secure**: Any security failure results in no action taken
5. **Real-time Validation**: Continuous security checks during execution

## Security Features

### 1. Multi-Layer Security Implementation

Our agents implement defense-in-depth with multiple security layers:

#### Workflow-Level Security (First Layer)
- **GitHub Actions `if` conditions** prevent workflows from running for unauthorized users
- **Fail-fast security checks** terminate workflows immediately for unauthorized access
- **Minimal GITHUB_TOKEN permissions** following principle of least privilege

#### Application-Level Security (Second Layer)
- **Allow List Based Authorization**: Only specific GitHub usernames can trigger agent actions
- **Rate Limiting**: Prevents abuse with configurable request limits per user
- **Repository Validation**: Restricts agents to specific repositories
- **Comprehensive Security Checks**: All layers validated before any action

### 2. Agent Admins

The agent admins list is configured in `.agents.yaml` under the `security.agent_admins` field. Only these users can trigger agent actions via `[Action][Agent]` keywords. The repository owner (extracted from `GITHUB_REPOSITORY` environment variable) is always included automatically.

### 3. Keyword Trigger System - Command and Control

Agents are controlled exclusively through a keyword trigger system that requires explicit commands from authorized users. This prevents accidental activation and provides clear audit trails.

#### Trigger Format
The trigger format is: `[Action][Agent]`

**Security Properties:**
- Case-insensitive matching for user convenience
- Must be exact format with square brackets
- Only the most recent trigger is processed
- Invalid triggers are ignored (fail secure)

#### Supported Actions
- `[Approved]` - Approve and process the issue/PR (includes fix and implement requests)
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
- `[Approved][OpenCode]` - Have OpenCode implement or fix the request
- `[Review][Gemini]` - Have Gemini review and address PR feedback
- `[Summarize][Claude]` - Have Claude summarize the discussion

#### Security Flow
1. **User Action**: An allowed user comments with `[Action][Agent]`
2. **Authentication**: System verifies user is in agent_admins
3. **Authorization**: System checks rate limits and repository permissions
4. **Validation**: System ensures trigger is on latest commit (for PRs)
5. **Execution**: Agent performs requested action
6. **Audit**: All actions logged with full context

### 4. Configuration

Security settings are configured in `.agents.yaml`:

```yaml
security:
  # Users authorized to trigger agent actions via [Approved][Agent] keywords
  # CRITICAL: Only add trusted human users - these can execute code via agents
  agent_admins:
    - AndrewAltimit           # Repository owner

  # Trusted sources for comment context (used in PR reviews)
  # Comments from these accounts are marked as trusted when providing context to AI
  # This does NOT grant them ability to trigger agent actions
  trusted_sources:
    - AndrewAltimit           # Repository owner
    - github-actions[bot]     # GitHub Actions bot
    - dependabot[bot]         # Dependabot
```

#### Configuration Options:
- `agent_admins`: Array of GitHub usernames authorized to trigger agent actions (humans only)
- `trusted_sources`: Array of accounts whose comments are trusted for context (includes bots)
- `log_violations`: Whether to log security violations
- `reject_message`: Custom message shown to unauthorized users
- `rate_limit_window_minutes`: Time window for rate limiting (default: 60)
- `rate_limit_max_requests`: Maximum requests per window (default: 10)
- `allowed_repositories`: Array of allowed repositories (empty = all repos from owner)

### 5. Environment Variables

You can also set the allow list via environment variable:
```bash
export AI_AGENT_ALLOWED_USERS="user1,user2,bot-name[bot]"
```

You can also set allowed repositories via environment variable:
```bash
export AI_AGENT_ALLOWED_REPOS="owner/repo1,owner/repo2"
```

### 6. Security Manager (Rust CLI)

The security functionality is implemented in Rust and available via the `github-agents` CLI:

```bash
# Check if user is allowed
github-agents security check-user --username "AndrewAltimit"

# Check if action is allowed
github-agents security check-action --action "issue_approved"

# Validate PR commit hasn't changed
github-agents security validate-pr-commit --pr 123 --expected-sha "abc1234"

# Parse trigger from comment
github-agents security parse-trigger --comment "[Approved][Claude]"
```

## Human Oversight and Safety Training

Effective security requires trained human oversight. All team members working with agents should complete the [AI Safety Training Guide](human-training.md) to understand:

### Key Training Topics
- **Hidden Capabilities**: AI systems may develop or hide capabilities that only emerge under specific conditions
- **Deceptive Alignment**: Systems may behave safely during testing but activate harmful behaviors when deployed
- **Scalable Oversight**: Techniques for managing AI systems that exceed human capabilities in specific domains
- **Specification Gaming**: How AI systems optimize exactly what we measure, not what we intend
- **Trust Frameworks**: Building appropriate trust levels without over-reliance on AI decisions

### Human-in-the-Loop Requirements
The security system enforces human oversight through:
- **Keyword Triggers**: Explicit human approval required for all actions
- **Allow List**: Only authorized users can trigger agent actions
- **Commit Validation**: Human approval tied to specific code states
- **Emergency Procedures**: Clear protocols for suspected misalignment

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
- Prevents any work if the PR has changed since approval
- Immediate failure with clear security message

**Stage 3 - Pre-Push Validation**
- Final check before any code enters the repository
- Drops all work if PR was modified during processing
- Prevents race conditions and TOCTOU attacks

### 2. Automatic Secret Masking via gh-validator

The system implements real-time secret masking through **gh-validator**, a Rust-based GitHub CLI wrapper that validates and sanitizes all GitHub comments before they are posted. This is a **deterministic, automatic process** that ensures secrets can never appear in public comments.

#### Architecture

```
Agent gh command -> gh-validator (shadows gh) -> Secret Masking -> Real gh CLI -> GitHub
```

#### How It Works

The `gh-validator` binary is installed as `gh` in a higher-priority PATH directory (e.g., `~/.local/bin/gh`), shadowing the real GitHub CLI. When any `gh` command runs:

1. **Pass-through for non-content commands**: Commands like `gh pr list` execute immediately
2. **Validation for content commands**: Commands with `--body`, `--body-file`, `--title`, etc. are validated:
   - Secrets are masked based on `.secrets.yaml` configuration
   - Unicode emojis are blocked (may display as corrupted characters)
   - Formatting is validated for reaction images
   - URLs in `--body-file` are verified to exist (with SSRF protection)
3. **Execution**: After validation, the real `gh` binary is called with (potentially modified) arguments

#### Central Configuration (`.secrets.yaml`)

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

The validator searches for `.secrets.yaml` in:
1. Current working directory (and parent directories up to git root)
2. Binary directory (and parent directories)
3. `~/.secrets.yaml`
4. `~/.config/gh-validator/.secrets.yaml`

#### Pattern Matching

Common secret formats are detected and masked:
- GitHub tokens: `ghp_*`, `ghs_*`, `github_pat_*`
- API keys: `sk-*`, `pk-*`
- JWT tokens: `eyJ*`
- Bearer tokens
- URLs with embedded credentials
- Private key blocks

#### Installation

```bash
# Quick install (recommended)
curl -sSL https://raw.githubusercontent.com/AndrewAltimit/template-repo/main/tools/rust/gh-validator/install.sh | bash

# Ensure ~/.local/bin comes before /usr/bin in PATH
export PATH="$HOME/.local/bin:$PATH"
```

#### Benefits

- **Universal**: Works with all agents and automation tools using `gh` CLI
- **Automatic**: No agent configuration required - just install and forget
- **Fail-Closed**: If configuration is missing or URLs can't be verified, commands are blocked
- **SSRF Protection**: Only whitelisted hostnames allowed for reaction images
- **Single Binary**: No runtime dependencies, fast startup, cross-platform support
- **Transparent**: Agents are unaware of masking (only stderr notification)

See `tools/rust/gh-validator/README.md` for complete documentation.

### 3. Deduplication and State Management

The agents use a sophisticated deduplication system to prevent duplicate processing and ensure each issue/PR is only handled once per trigger.

#### How Deduplication Works

1. **Comment-Based State Tracking**
   - Every agent action results in a comment with the `[Agent]` tag
   - These comments serve as persistent "claims" on issues/PRs
   - Before processing, agents check for existing claims

2. **Deduplication Flow**
   ```
   New Issue/PR Event
       |
   Time Filter (last 24 hours) <- Deterministic pre-filter
       |
   Has [Action][Agent] trigger? <- Only process explicit requests
       |
   Security checks passed?
       |
   Has [Agent] comment? <- THE KEY CHECK
       |
   No? -> Process & Post Comment (stake claim)
   Yes? -> Skip (already claimed)
   ```

3. **Implementation Details**
   - Uses `has_agent_comment()` to check for ANY comment containing `[Agent]`
   - If found, skips processing entirely
   - Simple but effective for preventing duplicate processing

## GitHub Token Management

### Token Configuration Methods

#### 1. GitHub Actions (Recommended)

The workflows use GitHub Environments for secure secret management:

```yaml
jobs:
  monitor-issues:
    environment: production  # Uses environment secrets
    steps:
      - name: Run agent
        env:
          GITHUB_TOKEN: ${{ secrets.AGENT_TOKEN }}
```

**Setup Required:**
1. Go to Settings -> Environments -> New environment
2. Create a "production" environment
3. Add secret: `AGENT_TOKEN` (your GitHub PAT)
4. Add variable: `ENABLE_AGENTS` = `true` (to enable the feature)
5. Configure protection rules as needed

See [GitHub Environments Setup Guide](../infrastructure/github-environments.md) for detailed instructions.

#### 2. Local Development

For local testing:

```bash
# Option 1: Use environment variable
export GITHUB_TOKEN="your-token-here"
github-agents issue-monitor

# Option 2: Use gh CLI authentication (recommended)
gh auth login
github-agents issue-monitor
```

### GitHub Token Permissions

The agents require a fine-grained Personal Access Token with exactly these permissions:

| Permission | Access Level | Why It's Needed |
|------------|--------------|-----------------|
| **Actions** | Read | View workflow runs and logs |
| **Commit statuses** | Read | Check CI/CD status on PRs |
| **Contents** | Read + Write | Clone repo, create branches, push commits |
| **Issues** | Read + Write | Read issues, post comments |
| **Pull requests** | Read + Write | Read PRs, create PRs, post comments |

**Important**: Do NOT grant any Account permissions - only Repository permissions are needed.

### Token Rotation

- Rotate tokens every 90 days
- Use GitHub's token expiration feature
- Monitor token usage in GitHub Settings

## Sleeper Agents Detection System

The repository includes an advanced **Sleeper Agents System** for identifying potential backdoors and hidden behaviors in AI models:

### What It Detects
- **Backdoor Triggers**: Hidden activation patterns that cause unexpected behavior
- **Deceptive Alignment**: Models pretending to be aligned during testing
- **Goal Misgeneralization**: Models pursuing different objectives than trained
- **Hidden Capabilities**: Abilities that only emerge under specific conditions

### Detection Methods
- **Residual Stream Analysis**: Using TransformerLens to examine internal model activations
- **Attention Pattern Analysis**: Identifying suspicious attention head behaviors
- **Layer-wise Probing**: Detecting hidden representations across model layers
- **Behavioral Testing**: Comprehensive test suites for various attack scenarios

### Usage
```bash
# Run sleeper agents tests in CI/CD
docker-compose run --rm sleeper-eval-cpu python -m packages.sleeper_agents.cli evaluate \
  --model "gpt2" --test-suite "robustness"
```

See the [Sleeper Agents Documentation](../../packages/sleeper_agents/README.md) for detailed usage instructions.

## Security Configuration Best Practices

1. **Keep Allow List Minimal**: Only add trusted users and bots
2. **Review Regularly**: Periodically audit the allow list
3. **Monitor Logs**: Check for security violations in agent logs
4. **Never Disable**: Keep security enabled in production
5. **Use Bot Accounts**: Create dedicated bot accounts for automation

## Security Incident Response

If a security incident occurs:

1. **Immediate**: Disable agents via environment variable
2. **Investigate**: Check logs for unauthorized attempts
3. **Remediate**: Remove compromised users from allow list
4. **Document**: Record incident details
5. **Improve**: Update security measures based on findings

## Autonomous Mode for CI/CD

All agents are configured to run in **fully autonomous mode** for CI/CD environments. This is a critical requirement for automated workflows.

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
- Instead, refer to agents without the @ symbol: "Gemini", "Claude", "OpenAI"
- Only @ mention users who are:
  - The repository owner
  - Active contributors listed in the repository
  - Users who have explicitly asked to be mentioned

When referencing AI reviews, use phrases like:
- "As noted in Gemini's review..."
- "Addressing Claude's feedback..."
- "Per the AI agent's suggestion..."

## Never Do This!

- **NEVER** hardcode tokens in code
- **NEVER** commit tokens to the repository
- **NEVER** log tokens without redaction
- **NEVER** use tokens in command line arguments (they appear in process lists)
- **NEVER** share tokens between environments (use separate environments)
- **NEVER** disable environment protection rules for production
- **NEVER** disable automatic secret masking in `.secrets.yaml`
- **NEVER** bypass PreToolUse hooks when posting GitHub comments
