# Security Policy

## AI Agent Security

This repository uses AI agents with a comprehensive multi-layer security model.

**For complete security documentation, see:** [`docs/agents/security.md`](docs/agents/security.md)

## Quick Reference

### Emergency Kill Switch
- Set `ENABLE_AGENTS=false` in GitHub Variables to disable all agents immediately
- Delete `AGENT_TOKEN` from secrets as a last resort

### Security Model Overview
- **Command-based control**: `[Action][Agent]` format prevents prompt injection
- **User authorization**: Only pre-approved users can trigger agents
- **Commit validation**: Prevents code injection after approval
- **Automatic secret masking**: Real-time masking in GitHub comments via PreToolUse hooks
- **Environment isolation**: Agents restricted to development environments only
- **Centralized secrets config**: `.secrets.yaml` defines all sensitive patterns

### Reporting Security Vulnerabilities

If you discover a security vulnerability in this repository:

1. **Do NOT** create a public issue
2. **Do NOT** trigger AI agents on the vulnerability
3. **Contact**: Create a private security advisory via GitHub's Security Advisory feature

The maintainer may or may not respond to vulnerability reports. This repository does not maintain a bug bounty program and does not guarantee acknowledgment, response, or remediation timelines. See [CONTRIBUTING.md](CONTRIBUTING.md) for the project's policy on external engagement.

## Additional Resources

- **Full Security Documentation**: [`docs/agents/security.md`](docs/agents/security.md)
- **Agent Architecture**: [`docs/agents/containerization-strategy.md`](docs/agents/containerization-strategy.md)
- **Claude Authentication**: [`docs/agents/claude-auth.md`](docs/agents/claude-auth.md)
- **GitHub Agents CLI**: [`tools/rust/github-agents-cli/`](tools/rust/github-agents-cli/) (Rust implementation)

## Disclaimer

This repository contains dual-use security research and tooling. The maintainer provides no guarantees regarding the security of any component. All code is provided as-is. The maintainer assumes no liability for security issues arising from use of this code and no obligation to respond to security reports. Users are responsible for their own security assessments before deploying any component.
