# Developer Documentation

Tools, configuration, and best practices for developers working with this codebase.

## Documentation

### [Claude Code Hooks and gh-validator](./claude-code-hooks.md)
The repo configures no Claude Code hooks (`.claude/settings.json` is `{}`); guardrails are enforced by the `gh-validator` and `git-guard` wrapper binaries instead. Covers gh-validator installation, validation rules, and troubleshooting.

## Developer Tools

### AI Agent Configuration
The project uses multiple AI agents for development. Key files:
- `AGENTS.md` - Universal AI agent configuration
- `CLAUDE.md` - Claude-specific instructions
- `.claude/settings.json` - Claude Code settings (intentionally `{}`)
- `.mcp.json` - MCP server configuration

### Development Commands

```bash
# Run full CI pipeline
automation-cli ci run full

# Format code
automation-cli ci run autoformat

# Run tests
automation-cli ci run test

# Check linting
automation-cli ci run lint-full
```

### Container Development

All Python operations run in Docker containers:

```bash
# Start development containers
docker compose up -d

# Run Python commands in container
docker compose run --rm python-ci python script.py

# View logs
docker compose logs -f
```

## Best Practices

1. **Always use containers** for Python operations
2. **Run CI checks** before committing
3. **Install the wrapper guards** (`gh-validator`, `git-guard`)
4. **Use MCP servers** for specialized tasks
5. **Test in containers** to ensure consistency

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Environment variables |
| `docker-compose.yml` | Container services |
| `.mcp.json` | MCP server configuration |
| `pyproject.toml` | Python project configuration |

## Related Documentation

- [Main Documentation](../README.md)
- [AGENTS.md](../../AGENTS.md) - Universal AI agent configuration
- [Infrastructure Setup](../infrastructure/)
- [MCP Architecture](../mcp/)
- [AI Agents](../agents/)
