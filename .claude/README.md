# Claude Code Settings

The `.claude/settings.json` file is intentionally empty (`{}`).

This project uses the `gh-validator` Rust binary for GitHub comment security. The binary is installed at `~/.local/bin/gh` and shadows the system `gh` command via PATH ordering.

## Security Features

The gh-validator automatically:
- Masks secrets from environment variables and regex patterns
- Blocks Unicode emojis (display as corrupted characters)
- Validates reaction image URLs (SSRF protection)
- Blocks stdin usage for security

## Setup

1. Install the gh-validator binary (see `tools/rust/gh-validator/install.sh`)
2. Ensure `~/.local/bin` is first in your PATH:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

The empty JSON object ensures compatibility with Claude Code while indicating that no hooks are configured. This is the recommended approach as it:
- Guarantees Claude Code won't error on missing file
- Clearly shows no hooks are in use
- Maintains forward compatibility

For more information, see:
- `tools/rust/gh-validator/README.md` - gh-validator documentation
- `docs/developer/claude-code-hooks.md` - Security system overview
