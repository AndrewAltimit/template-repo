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

#### Agent Admin Capabilities

Agent admins have the following special capabilities:

1. **Trigger Agent Actions**: Use `[Action][Agent]` keywords to invoke agents
2. **Extend Iteration Limits**: Use `[CONTINUE]` to allow more agent iterations (see below)
3. **Authoritative Comments**: Their comments are treated as authoritative in review contexts

### 3. Agent Iteration Limits and Continue

To prevent infinite loops where agents repeatedly try to fix the same issues, the system tracks iteration counts based on PR comments. Each agent type has its own independent counter.

#### How Iteration Tracking Works

- **Comment-Based Tracking**: Iterations are counted by parsing PR comments with agent metadata markers
- **Separate Counters**: The `review-fix` agent (responds to AI reviews) and `failure-fix` agent (responds to CI failures) have independent iteration counts
- **Max Iterations**: By default, each agent is limited to 5 iterations before pausing
- **Metadata Format**: Comments include `<!-- agent-metadata:type=TYPE:iteration=N -->` for tracking

#### The `[CONTINUE]` Command

Agent admins can extend an agent's iteration limit by posting a comment containing `[CONTINUE]`:

```
[CONTINUE]

I've reviewed the progress. Let the agent continue working on this.
```

**How it works:**
- Each `[CONTINUE]` **adds** the base limit to the effective max
- Base limit is 5, so: 1x `[CONTINUE]` = max 10, 2x `[CONTINUE]` = max 15, etc.
- The iteration count itself is not reset - it keeps incrementing

**Key Details:**
- **Case-insensitive**: `[CONTINUE]`, `[continue]`, and `[Continue]` all work
- **Admin-only**: Only users in `security.agent_admins` can extend limits
- **Cumulative**: Multiple `[CONTINUE]` comments stack (each adds 5 more iterations)
- **Per-PR**: The count applies to the entire PR comment history

#### Example Scenario

1. PR validation runs, agent tries to fix issues (iterations 1-5)
2. Agent hits max iterations (5), posts "Iteration Limit Reached" message
3. Human reviews progress and decides the agent should continue
4. Admin comments: `[CONTINUE] Making good progress, keep going`
5. Effective max is now 10 - agent can run iterations 6-10
6. If needed, another `[CONTINUE]` would extend to 15, and so on

#### Configuration

```yaml
# In .agents.yaml
automation:
  max_auto_fix_iterations: 5  # Base limit per agent (extended by [CONTINUE])
```

### 4. Keyword Trigger System - Command and Control

Agents are controlled exclusively through a keyword trigger system that requires explicit commands from authorized users. This prevents accidental activation and provides clear audit trails.

#### Trigger Format
The trigger format is: `[Action][Agent]`

The `[Agent]` part is optional; without it the highest-priority available agent is used. An explicitly requested agent is never silently replaced: if it is unknown, disabled or not installed, the request fails with a clear message.

**Security Properties:**
- Case-insensitive matching for user convenience
- Must be exact format with square brackets
- Triggers inside fenced code blocks, inline code spans, blockquotes and HTML comments are ignored, so quoting or documenting a trigger never fires it and invisible text can never authorize anything
- Comments generated by the tool itself (hidden `<!-- github-agents:... -->` markers or the legacy `[AI Agent]` prefix) are never treated as triggers, even when posted under an allow-listed account
- Comments are scanned newest first, so only the **latest authorized** trigger counts; the issue/PR body is only considered when no comment carries one
- Each trigger is acted on once: a monitor reply carrying the trigger-response marker from a trusted account marks it handled
- Bot accounts (`*[bot]`, `github-actions`) are never authorized
- All model output is neutralized before posting (`[Approved]` becomes `\[Approved\]`), so a prompt-injected agent cannot approve its own work
- Invalid triggers are ignored (fail secure)

#### Supported Actions
- `[Approved]` - Approve and process the issue/PR (includes fix and implement requests)
- `[Review]` - Review and address feedback
- `[Close]` - Close the issue/PR
- `[Summarize]` - Provide a summary
- `[Debug]` - Debug the issue

#### Supported Agents
- `[Claude]` - Claude Code agent
- `[OpenRouter]` - OpenRouter API agent (text-only responses, no code changes)
- `[OpenCode]` - Open-source coding AI
- `[Crush]` - Charm Bracelet Crush AI shell assistant

Gemini and Codex are disabled; `[Gemini]`/`[Codex]` triggers are rejected with a policy error.

#### Examples
- `[Approved][Claude]` - Have Claude process the issue/PR
- `[Approved][OpenCode]` - Have OpenCode implement or fix the request
- `[Review][Claude]` - Have Claude review and address PR feedback
- `[Summarize][Claude]` - Have Claude summarize the discussion

#### Security Flow
1. **User Action**: An allowed user comments with `[Action][Agent]`
2. **Authentication**: System verifies user is in agent_admins
3. **Authorization**: System checks the action against `allowed_actions`, the repository against `allowed_repositories`, and the per-user rate limit
4. **Validation**: For PR approvals, the head commit is pinned (see [Commit-Level Validation](#1-commit-level-validation-for-pull-requests))
5. **Execution**: Agent performs requested action
6. **Audit**: All actions logged with full context

### 5. Configuration

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
- `agent_admins`: Array of GitHub usernames authorized to trigger agent actions (humans only; bot accounts are never authorized)
- `trusted_sources`: Array of accounts whose comments are trusted for context (includes bots). Also used by `board-manager` for claim authorship (see [Board Claims and Approvals](#4-board-claims-and-approvals))
- `enabled`: Whether security checks are enabled (default: true)
- `allowed_actions`: Actions that may be triggered (default: `issue_`/`pr_` variants of `approved`, `review`, `summarize`, `debug`, `close`)
- `reject_message`: Custom message shown to unauthorized users
- `rate_limit_window_minutes`: Time window for rate limiting (default: 60)
- `rate_limit_max_requests`: Maximum requests per window (default: 10)
- `allowed_repositories`: Array of allowed repositories (empty = all repositories)

A config file that exists but is invalid is a hard error for the monitors (fail secure).

### 6. Environment Variables

You can also add users to the allow list via environment variable (bot accounts listed here are still never authorized):
```bash
export AI_AGENT_ALLOWED_USERS="user1,user2"
```

Allowed repositories are configured only through `allowed_repositories` in `.agents.yaml`.

When no `.agents.yaml` is present, the security manager falls back to a
built-in default admin. Override it (comma-separated) without editing config:
```bash
export AI_AGENT_DEFAULT_ADMIN="owner1,owner2"
```

### 7. Security Manager (Rust CLI)

The security functionality is implemented in Rust and available via the `github-agents` CLI (`tools/rust/github-agents-cli`):

```bash
github-agents security [--config .agents.yaml] [--format text|json] <command>

# Check if user is allowed (exit 8 if not allow-listed)
github-agents security check-user --username "AndrewAltimit"

# Check if action is allowed (exit 8 if not)
github-agents security check-action --action "issue_approved"

# Validate PR head commit matches the approved SHA (exit 8 on mismatch)
github-agents security validate-pr-commit --pr 123 --expected-sha "abc1234" [--repo owner/repo]

# Parse trigger from comment (prints action/agent, or "No trigger found")
github-agents security parse-trigger --comment "[Approved][Claude]"
```

`--config` (default `.agents.yaml`) and `--format` (default `text`) are accepted before or after the subcommand. `--expected-sha` must be 7-64 hex characters; `--repo` defaults to `GITHUB_REPOSITORY`. With `--format json` the commands print `{username, allowed}`, `{action, allowed}`, `{pr, expected_sha, head_sha, valid}` and `{found, action, agent}` respectively. A failed check exits with code 8 (security check failed); `parse-trigger` applies the same code-span, blockquote and HTML-comment filtering as the monitors.

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

The PR monitor (`github-agents pr-monitor`) pins PR approvals to a commit to prevent code injection attacks during the review and modification process.

#### The Threat Model
Without commit validation, an attacker could:
1. Create an innocent-looking PR
2. Wait for approval from an authorized user
3. Push malicious code after approval but before (or while) the agent works on the branch
4. Have the AI agent unknowingly work on and push malicious code

#### Our Multi-Stage Defense

**Stage 1 - Approval Freshness**
- The PR head commit must not be newer than the `[Approved][Agent]` comment
- Commit dates are client-supplied, so this catches ordinary pushes but not deliberately back-dated commits; stages 2 and 3 are the authoritative checks

**Stage 2 - Pre-Execution Pin**
- The head SHA observed when the trigger was discovered must still be the head SHA right before the agent starts
- Prevents any work if the PR has changed; re-approval is requested

**Stage 3 - Pre-Publish Pin**
- The head SHA must be unchanged after the agent finishes
- Otherwise all agent output is discarded and re-approval is requested
- Prevents race conditions and TOCTOU attacks

The same SHA comparison is available standalone as `github-agents security validate-pr-commit`.

In workflows triggered by pull request events, `.agents.yaml`, `review-profiles.yaml`, `README.md`/`CLAUDE.md` context and `.mcp.json` are taken from the base branch when the PR modifies them (`.mcp.json` is skipped entirely in that case), so a PR cannot weaken its own security configuration.

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

The validator searches for `.secrets.yaml` in this order (first existing file wins):
1. `/etc/wrapper-guard/.secrets.yaml` (root-owned system config, e.g. the hardened container)
2. Current working directory (and parent directories up to git root)
3. Binary directory (and parent directories up to a git root)
4. `~/.secrets.yaml`
5. `$XDG_CONFIG_HOME/gh-validator/.secrets.yaml` (default `~/.config/gh-validator/.secrets.yaml`)

#### Pattern Matching

A built-in baseline is always active, even with a weakened config: the values of `GITHUB_TOKEN`, `GH_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`, `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY`, plus GitHub token, AWS key, Anthropic key, Slack token and private-key-block formats. The repository `.secrets.yaml` adds further patterns, for example:
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

Both `git-guard` and `gh-validator` are hardened against bypass through the **Wrapper Guard** system, which relocates real binaries behind group-restricted permissions and provides structured audit logging. See [Wrapper Guard Documentation](../infrastructure/wrapper-guard.md) for the full security model.

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
   - Monitor replies carry a hidden `<!-- github-agents:trigger-response -->` marker (older replies use the visible `[AI Agent]` prefix)
   - A trigger followed by such a reply from a trusted account (allow-listed user, bot, or the agent's own account) is treated as handled and skipped
   - This makes monitor runs idempotent: the same `[Approved]` comment is never acted on twice, and security rejections are not re-posted on every polling cycle

### 4. Board Claims and Approvals

The project-board workflow (`board-manager`, see [Board Workflow](board-workflow.md)) applies the same trust model to work claims and approvals:

**Claim authorship**
- Claims are structured issue comments (`[Agent Claim]`, `[Claim Renewal]`, `[Agent Release]`)
- Only claim, renewal and release comments written by a user in `security.agent_admins` or `security.trusted_sources` of `.agents.yaml` count (case-insensitive; GitHub App authors such as the Actions bot match their `name[bot]` entry, e.g. `github-actions[bot]`)
- Look-alike comments from anyone else are ignored, so they cannot squat on, renew or release a claim
- If `.agents.yaml` cannot be loaded, only comments by the repository owner count (fail closed)
- This applies to `claim`, `renew`, `janitor` and every other command that reads claims

**Approval**
- Only an `[Approved][Agent]` trigger (case-insensitive) in the issue body or a comment approves an issue; `[Review]`, `[Close]`, `[Summarize]` and `[Debug]` are not approvals
- It counts only when written by the project owner, the repository owner, or a user in `security.agent_admins`; `trusted_sources` cannot approve
- When an agent is given (`ready --agent A --approved-only`, `check-approval --agent A`, `find-approved --agent A`), the trigger must name that agent; workflow and board names are equivalent (`[Approved][Claude]` and `[Approved][Claude Code]` both approve for `claude`)

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
docker compose run --rm sleeper-eval-cpu python -m packages.sleeper_agents.cli evaluate \
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
