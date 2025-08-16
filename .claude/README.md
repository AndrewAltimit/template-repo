# Claude Code Settings

The `.claude/settings.json` file is intentionally empty (`{}`).

This project uses a universal security wrapper approach where ALL agents (including Claude Code) use the same `gh-wrapper.sh` through shell aliasing. No agent-specific hooks are needed.

To enable security hooks for Claude Code:
1. Restart Claude Code
2. The security hooks are automatically set up via ~/.bashrc

The empty JSON object ensures compatibility with Claude Code while indicating that no hooks are configured. This is the recommended approach as it:
- Guarantees Claude Code won't error on missing file
- Clearly shows no hooks are in use
- Maintains forward compatibility

For more information, see:
- `automation/security/README.md` - Universal security hooks documentation
- `docs/developer/claude-code-hooks.md` - Migration guide from old hooks
