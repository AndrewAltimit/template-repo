# Security Policy

## AI Agent Security Model

This repository uses AI agents that implement a comprehensive security model with deterministic processes to prevent unauthorized access, secret exposure, and malicious code injection.

### Quick Security Reference

| Component | Security Measure | Purpose |
|-----------|-----------------|---------|
| **Kill Switch** | `ENABLE_AI_AGENTS` variable | Emergency shutdown control |
| **Environment** | DEV-only access for agents | Prevents production access |
| **Commands** | `[Action][Agent]` format only | Prevents prompt injection |
| **Users** | Allow list in `config.json` | Prevents unauthorized access |
| **Commits** | SHA validation before/after work | Prevents code injection |
| **Secrets** | Multi-layer masking system | Prevents credential exposure |
| **Filtering** | Time + Trigger + Security checks | Deterministic issue selection |
| **Implementation** | Full completion required | Prevents incomplete/vulnerable code |
| **Rate Limits** | Per-user request limits | Prevents resource abuse |

### Kill Switch and Environment Controls

#### Master Kill Switch

The `ENABLE_AI_AGENTS` environment variable serves as a master kill switch:

```yaml
# In GitHub Actions workflows
if: vars.ENABLE_AI_AGENTS == 'true'
```

**To disable agents immediately:**
1. GitHub Settings → Variables → Set `ENABLE_AI_AGENTS=false`
2. GitHub Settings → Actions → Disable workflows
3. Emergency: Delete `AI_AGENT_TOKEN` from secrets

#### Environment Isolation

AI agents should **ONLY** have access to development environments:

```
Production:  ❌ No AI agent access
Staging:     ❌ No AI agent access
Development: ✅ Limited AI agent access
```

This prevents AI agents from accessing production secrets or infrastructure, even if security controls are bypassed.

### How to Trigger AI Agents Securely

1. **Be an authorized user** (check security configuration)
2. **Use exact command format**: `[Action][Agent]`
3. **Valid commands**:
   - `[Approved][Claude]` - Process issue/PR
   - `[Fix][Claude]` - Fix a bug
   - `[Implement][Claude]` - Implement a feature
   - `[Review][Claude]` - Address PR feedback
   - `[Close][Claude]` - Close issue/PR
   - `[Summarize][Claude]` - Summarize
   - `[Debug][Claude]` - Debug issue

## Deterministic Security Processes

### 1. Secret Masking for Agent Outputs

The system implements multi-layer secret masking to prevent credential exposure:

**Automatic Detection & Masking:**
- GitHub tokens: `ghp_*`, `github_pat_*` → `[REDACTED]`
- API keys: `sk-*`, `pk-*`, Bearer tokens → `[REDACTED]`
- Environment variables: Values replaced with `[VARIABLE_NAME]`
- URLs with credentials: `https://user:pass@site` → `https://[REDACTED]@site`

**Implementation Layers:**
1. **Logging Layer**: `SecretRedactionFilter` in all Python logs
2. **Output Layer**: `mask_secrets()` for all GitHub comments
3. **Error Masking**: Failed command outputs are sanitized
4. **Environment Variables**: Configurable via `MASK_ENV_VARS`

**Example:**
```python
# Original error output:
"Error: Invalid GITHUB_TOKEN=ghp_1234567890abcdef"

# Posted to PR comment:
"Error: Invalid GITHUB_TOKEN=[REDACTED]"
```

### 2. Deterministic Issue/PR Filtering

Issues and PRs are processed through a strict filtering pipeline:

```
New Issue/PR → Time Filter → Trigger Check → Security Validation → Deduplication → Processing
     ↓              ↓              ↓                   ↓                  ↓            ↓
   Drop if      Drop if no     Drop if user      Drop if rate      Drop if AI    Process
  >24h old    [Action][Agent]  not authorized    limit exceeded   already acted
```

**Filtering Steps:**
1. **Time Window**: Only issues/PRs updated within `cutoff_hours` (default: 24h)
2. **Keyword Trigger**: Must have `[Action][Agent]` from authorized user
3. **User Authorization**: User must be in `security.allow_list`
4. **Rate Limiting**: Max requests per user per time window
5. **Deduplication**: Skip if `[AI Agent]` comment already exists

**Configuration:**
```json
{
  "agents": {
    "issue_monitor": {
      "cutoff_hours": 24,
      "min_description_length": 50
    }
  },
  "security": {
    "allow_list": ["authorized-user"],
    "rate_limit_max_requests": 10
  }
}
```

### 3. Commit Validation Before Push

Prevents malicious code injection during PR processing:

**Three-Stage Validation:**

1. **Approval Recording** (When `[Approved][Claude]` is issued):
   ```python
   approval_commit_sha = get_pr_latest_commit(pr_number)
   # SHA is passed to work scripts via environment
   ```

2. **Pre-Work Validation** (Before starting work):
   ```python
   current_sha = get_pr_latest_commit(pr_number)
   if current_sha != approval_commit_sha:
       abort("PR has new commits since approval")
   ```

3. **Pre-Push Validation** (Before pushing changes):
   ```bash
   # In fix scripts
   if [ "$NEW_COMMITS" -gt 0 ]; then
       echo "ERROR: New commits detected after approval!"
       post_security_notice()
       exit 1
   fi
   ```

**Attack Prevention Example:**
```
Time 0: Attacker creates innocent PR
Time 1: Admin: [Approved][Claude]
Time 2: Agent records SHA: abc123
Time 3: Attacker pushes malicious commit (SHA: xyz789)
Time 4: Agent checks: abc123 ≠ xyz789
Time 5: Agent aborts with security notice ✓
```

### Security Features in Action

#### Example: Safe PR Review
```yaml
# Authorized user comments on PR
[Approved][Claude]

# Agent:
1. Records commit SHA: abc123
2. Validates user is authorized ✓
3. Starts working on changes
4. Before pushing: checks if PR still at commit abc123
5. If yes: pushes changes ✓
6. If no: aborts and requests new approval ✓
```

#### Example: Blocked Attack
```yaml
# Attack attempt:
1. Attacker creates PR
2. Authorized user: [Approved][Claude]
3. Attacker pushes malicious commit
4. Agent detects new commit ≠ approved commit
5. Agent aborts all work ✓
6. Posts security notice ✓
```

### Reporting Security Vulnerabilities

If you discover a security vulnerability:

1. **Do NOT** create a public issue
2. **Do NOT** trigger AI agents on the vulnerability
3. **Contact**: Create a private security advisory or contact the repository owner directly
4. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Security Checklist for Maintainers

- [ ] Regularly review `security.allow_list` in `config.json`
- [ ] Monitor agent logs for unauthorized attempts
- [ ] Keep `ENABLE_AI_AGENTS` disabled unless actively using
- [ ] Review all PRs created by AI agents before merging
- [ ] Audit agent actions monthly
- [ ] Test security with non-authorized users quarterly
- [ ] Ensure AI agents only have DEV environment access
- [ ] Require PR reviews for `.github/workflows` changes
- [ ] Monitor for workflow file modifications

### Additional Security Documentation

- **Full Documentation**: See `packages/github_ai_agents/docs/security.md`
- **Configuration**: See agent configuration in environment
- **Logs**: Check GitHub Actions logs for security events

### Known Limitations and Accepted Risks

#### Developer Override Risk

Developers with repository write access can potentially modify `.github/workflows` files to bypass security controls. This is an accepted risk that we mitigate through:

1. **Environment Isolation**: AI agents are restricted to development environments only
2. **Branch Protection**: Protect `.github/workflows` directory with required reviews
3. **Audit Trail**: All workflow modifications are logged in git history
4. **Monitoring**: Regular reviews of workflow changes

#### Mitigation Strategy

```yaml
# Example branch protection rule for .github/workflows
paths:
  - '.github/workflows/**'
required_reviews: 2
dismiss_stale_reviews: true
```

## Responsible Disclosure

We take security seriously and appreciate responsible disclosure. Security researchers who report vulnerabilities responsibly may be acknowledged in our security updates.
