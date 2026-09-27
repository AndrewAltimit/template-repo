# Documentation

Project documentation, organized by category.

## Documentation Structure

### [Infrastructure](./infrastructure/)
DevOps, CI/CD, and self-hosted infrastructure setup
- [Self-Hosted Runner](./infrastructure/self-hosted-runner.md)
- [GitHub Environments](./infrastructure/github-environments.md)
- [Containerization](./infrastructure/containerization.md)
- [Git Hooks](./infrastructure/git-hooks.md)

### [Hardware](./hardware/)
Physical hardware systems for secure field deployment and biological automation
- [Secure Terminal Briefcase](./hardware/secure-terminal-briefcase.md): Tamper-responsive Pi briefcase with dual-sensor detection, LUKS2 wipe, and PQC recovery
- [BioForge CRISPR Automation](./hardware/bioforge-crispr-automation.md): Agent-driven biological automation with Pi 5, MCP tools, and closed-loop experiment orchestration
- [AI Agent Containment & Infrastructure Security](./hardware/ai-agent-containment-infrastructure-security-framework.md): Tiered trust model, isolation, agent-specific controls, and breakout response
- [Agent Swarm Honeypot Guide](./hardware/agent-swarm-honeypot-guide.md): Deception program design for detecting, attributing, and reporting autonomous agent swarms

### [AI Agents](./agents/)
AI agent system: roster, review pipeline, security
- [Overview](./agents/README.md)
- [Security](./agents/security.md)
- [Claude Authentication](./agents/claude-auth.md)
- [Agent Matrix](./agents/agent-matrix.md) (canonical roster; Gemini and Codex are legacy / not allowed)
- [Board Workflow](./agents/board-workflow.md)
- [AI Safety Training](./agents/human-training.md)
- [PR Monitoring](./agents/pr-monitoring.md)

### [MCP](./mcp/)
Model Context Protocol servers and architecture
- [Architecture Overview](./mcp/README.md)
- [Servers Reference](./mcp/servers.md)
- [Tools Reference](./mcp/tools.md)
- [STDIO vs HTTP Modes](./mcp/architecture/stdio-vs-http.md)

### [Integrations](./integrations/)
External service integrations
- **AI Services**
  - [AI Code Agents](./integrations/ai-services/ai-code-agents.md)
  - [OpenRouter Setup](./integrations/ai-services/openrouter-setup.md)
- **Creative Tools**
  - [AI Toolkit & ComfyUI](./integrations/creative-tools/ai-toolkit-comfyui.md)
  - [LoRA Transfer](./integrations/creative-tools/lora-transfer.md)

### [Developer](./developer/)
Developer tools and configuration
- [Claude Code Hooks and gh-validator](./developer/claude-code-hooks.md)

### [Guides](./guides/)
- [Agent Council Setup Guide](./guides/agent-council-setup-guide.md)

### [Roadmaps](./roadmaps/)
Planned work for MCP integrations, ElevenLabs, and the virtual character system

### [Projections](./projections/)
Scenario-based risk assessments of advanced AI agents (LaTeX reports plus Markdown summaries)

### [Philosophy](./philosophy/)
Philosophy papers on minds and experience, e.g. Architectural Qualia

## Quick Start

The [Template Quickstart Guide](./QUICKSTART.md) lists what to change when forking (addresses, keys, runners) and which features to keep or strip. It assumes you are comfortable with Docker, self-hosted runners, and autonomous agents; read the [AI Safety Training Guide](./agents/human-training.md) first.

## Additional Resources

- [Main README](../README.md) - Project overview
- [AGENTS.md](../AGENTS.md) - Universal AI agent configuration
- [CLAUDE.md](../CLAUDE.md) - Claude Code instructions
- [SECURITY.md](../SECURITY.md) - Security policies
