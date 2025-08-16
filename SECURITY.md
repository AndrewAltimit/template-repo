# Security Policy

## AI Agent Security

This repository uses AI agents with a comprehensive multi-layer security model.

**For complete security documentation, see:** [`packages/github_ai_agents/docs/security.md`](packages/github_ai_agents/docs/security.md)

## Quick Reference

### Emergency Kill Switch
- Set `ENABLE_AI_AGENTS=false` in GitHub Variables to disable all agents immediately
- Delete `AI_AGENT_TOKEN` from secrets as a last resort

### Security Model Overview
- **Command-based control**: `[Action][Agent]` format prevents prompt injection
- **User authorization**: Only pre-approved users can trigger agents
- **Commit validation**: Prevents code injection after approval
- **Automatic secret masking**: Real-time masking in GitHub comments via PreToolUse hooks
- **Environment isolation**: Agents restricted to development environments only
- **Centralized secrets config**: `.secrets.yaml` defines all sensitive patterns

### Reporting Security Vulnerabilities

1. **Do NOT** create a public issue
2. **Do NOT** trigger AI agents on the vulnerability
3. **Contact**: Create a private security advisory or contact the repository owner directly
4. **Include**: Description, steps to reproduce, impact, and suggested fix

## Additional Resources

- **Full Security Documentation**: [`packages/github_ai_agents/docs/security.md`](packages/github_ai_agents/docs/security.md)
- **Agent Architecture**: [`docs/ai-agents/containerization-strategy.md`](docs/ai-agents/containerization-strategy.md)
- **Claude Authentication**: [`docs/ai-agents/claude-auth.md`](docs/ai-agents/claude-auth.md)

## Responsible Disclosure

We take security seriously and appreciate responsible disclosure. Security researchers who report vulnerabilities responsibly may be acknowledged in our security updates.
