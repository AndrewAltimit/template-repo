# github-agents-cli

A fast Rust CLI for the GitHub AI Agents system.

## Overview

This tool provides a Rust-based command-line interface for the GitHub AI Agents monitoring system. All monitoring, analysis, and agent orchestration is implemented natively in Rust for fast startup times and single-binary distribution.

## Installation

```bash
# Build from source
cd tools/rust/github-agents-cli
cargo build --release

# The binary will be at target/release/github-agents
```

## Usage

```bash
# Run issue monitor once
github-agents issue-monitor

# Run issue monitor continuously (default: 5 minute intervals)
github-agents issue-monitor --continuous

# Run with custom interval (10 minutes)
github-agents issue-monitor --continuous --interval 600

# Run PR monitor once
github-agents pr-monitor

# Run PR monitor continuously
github-agents pr-monitor --continuous

# Enable verbose logging
github-agents -v issue-monitor
```

## Requirements

- GitHub CLI (`gh`) installed and authenticated
- Repository with proper `.agents.yaml` configuration

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | GitHub CLI not found or not authenticated |
| 3 | GitHub token not found |
| 130 | Interrupted by user (Ctrl+C) |

## Architecture

The CLI provides a complete native Rust implementation:

1. **Fast Startup**: Rust binary starts instantly
2. **Single Binary**: Easy distribution without external dependencies
3. **Signal Handling**: Graceful shutdown on Ctrl+C
4. **Native Implementation**: All monitoring, analysis, and agent orchestration runs natively in Rust

## Comparison with pr-monitor

For simple PR monitoring (watching for specific comments), use the dedicated `pr-monitor` tool:

```bash
# Simple PR comment monitoring
tools/rust/pr-monitor/target/release/pr-monitor 123

# Full PR monitoring with AI review processing (uses this CLI)
github-agents pr-monitor
```

## Development

```bash
# Run tests
cargo test

# Build release binary
cargo build --release

# Check formatting
cargo fmt --check

# Run clippy
cargo clippy
```

## License

MIT
