# Contributing

This repository does not accept external contributions. All code changes are authored by AI agents (Claude, Gemini, Codex, OpenCode, Crush) operating under human direction.

## Why no external contributions?

This is a single-maintainer project where the development workflow itself is the product. The entire CI/CD pipeline, agent orchestration system, and security model are tightly integrated and designed around autonomous agent authorship with human oversight. Accepting external PRs would break the assumptions that the tooling is built on.

## How to use this repo

- **Fork it.** Clone the repo and strip out what you don't need. The MCP servers, packages, and tools are modular -- take what's useful and leave the rest.
- **Study it.** The documentation covers agent orchestration patterns, trust measurement, security hardening, and containerized tooling that you can adapt to your own projects.
- **Report issues.** If you find a bug or have a question, open an issue. Fixes will be implemented by the repo's agent system, not by external contributors.

## What about issues?

Issues are welcome for bug reports and questions. However, issues in this repo are primarily used as work items for AI agents via the GitHub Projects v2 board. Agent-targeted issues are marked accordingly and processed automatically.
