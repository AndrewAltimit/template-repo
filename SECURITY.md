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
- **Secret masking**: Multi-layer system prevents credential exposure
- **Environment isolation**: Agents restricted to development environments only

### Reporting Security Vulnerabilities

1. **Do NOT** create a public issue
2. **Do NOT** trigger AI agents on the vulnerability
3. **Contact**: Create a private security advisory or contact the repository owner directly
4. **Include**: Description, steps to reproduce, impact, and suggested fix

## Additional Resources

- **Full Security Documentation**: [`packages/github_ai_agents/docs/security.md`](packages/github_ai_agents/docs/security.md)
- **Agent Architecture**: [`docs/AGENT_CONTAINERIZATION_STRATEGY.md`](docs/AGENT_CONTAINERIZATION_STRATEGY.md)
- **Claude Authentication**: [`docs/AI_AGENTS_CLAUDE_AUTH.md`](docs/AI_AGENTS_CLAUDE_AUTH.md)

## Responsible Disclosure

We take security seriously and appreciate responsible disclosure. Security researchers who report vulnerabilities responsibly may be acknowledged in our security updates.
