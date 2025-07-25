# Security Policy

## AI Agent Security Model

This repository uses AI agents that implement a comprehensive security model to prevent unauthorized access and malicious code injection.

### Quick Security Reference

| Component | Security Measure | Purpose |
|-----------|-----------------|---------|
| **Commands** | `[Action][Agent]` format only | Prevents prompt injection |
| **Users** | Allow list in `config.json` | Prevents unauthorized access |
| **Commits** | SHA validation before/after work | Prevents code injection |
| **Implementation** | Full completion required | Prevents incomplete/vulnerable code |
| **Rate Limits** | Per-user request limits | Prevents resource abuse |

### How to Trigger AI Agents Securely

1. **Be an authorized user** (check `scripts/agents/config.json`)
2. **Use exact command format**: `[Action][Agent]`
3. **Valid commands**:
   - `[Approved][Claude]` - Process issue/PR
   - `[Fix][Claude]` - Fix a bug
   - `[Implement][Claude]` - Implement a feature
   - `[Review][Claude]` - Address PR feedback
   - `[Close][Claude]` - Close issue/PR
   - `[Summarize][Claude]` - Summarize
   - `[Debug][Claude]` - Debug issue

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

### Additional Security Documentation

- **Full Documentation**: See `scripts/agents/README.md`
- **Configuration**: See `scripts/agents/config.json`
- **Logs**: Check GitHub Actions logs for security events

## Responsible Disclosure

We take security seriously and appreciate responsible disclosure. Security researchers who report vulnerabilities responsibly may be acknowledged in our security updates.
