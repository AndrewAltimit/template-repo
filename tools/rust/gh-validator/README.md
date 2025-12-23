# gh-validator

A Rust-based GitHub CLI wrapper that validates comments for security and formatting before posting.

## Features

- **Secret Masking**: Automatically detects and masks secrets in comment content
- **Unicode Emoji Detection**: Blocks emojis that may display as corrupted characters
- **Formatting Validation**: Ensures proper use of `--body-file` for reaction images
- **URL Validation**: Verifies reaction image URLs exist with SSRF protection
- **Cross-Platform**: Builds for Linux, macOS, and Windows

## Installation

### Quick Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/AndrewAltimit/template-repo/main/tools/rust/gh-validator/install.sh | bash
```

### Manual Installation

1. Download the binary for your platform from [Releases](https://github.com/AndrewAltimit/template-repo/releases)
2. Place it in `~/.local/bin/gh` (or another directory in your PATH)
3. Ensure `~/.local/bin` comes before `/usr/bin` in your PATH:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

## How It Works

The binary is named `gh` and shadows the real GitHub CLI. When you run any `gh` command:

1. If the command doesn't post content (e.g., `gh pr list`), it passes through immediately
2. If the command posts content (e.g., `gh pr comment`), validation runs:
   - Secrets are masked based on `.secrets.yaml` configuration
   - Unicode emojis are blocked
   - Formatting is validated for reaction images
   - URLs in `--body-file` are verified to exist
3. After validation, the real `gh` binary is called with (potentially modified) arguments

## Configuration

The validator looks for `.secrets.yaml` in:
1. Current working directory (and parent directories up to git root)
2. Binary directory (and parent directories)
3. `~/.secrets.yaml`
4. `~/.config/gh-validator/.secrets.yaml`

See the [.secrets.yaml template](../../../.secrets.yaml) for configuration options.

## Development

### Building from Source

```bash
cd tools/rust/gh-validator
cargo build --release
```

### Running Tests

```bash
cargo test
```

### Cross-Compiling

The CI/CD pipeline handles cross-compilation for all platforms. For local cross-compilation:

```bash
# Install cross
cargo install cross

# Build for Linux ARM
cross build --release --target aarch64-unknown-linux-gnu
```

## Architecture

```
src/
  main.rs           # Entry point, argument handling, exec
  lib.rs            # Library exports for testing
  error.rs          # Error types (thiserror-based)
  gh_finder.rs      # Real gh binary discovery
  config/
    mod.rs          # Config module exports
    types.rs        # Configuration struct definitions
    loader.rs       # YAML loading with search paths
  validation/
    mod.rs          # Validation module exports
    secrets.rs      # Secret masking logic
    comments.rs     # Emoji and formatting validation
    urls.rs         # URL validation with SSRF protection
```

## Security

- **Fail-Closed**: If configuration is missing or URLs can't be verified, commands are blocked
- **SSRF Protection**: Only whitelisted hostnames are allowed for reaction images
- **No IP Addresses**: Direct IPv4/IPv6 addresses are blocked
- **Single Binary**: No runtime dependencies, fast startup, cross-platform support
