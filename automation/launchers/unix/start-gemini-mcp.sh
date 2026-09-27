#!/bin/bash
# Thin wrapper: delegates to automation-cli Rust binary
# legacy: not allowed in this lab. Gemini code is kept for reference only.
if [ "${ALLOW_LEGACY_AGENTS:-}" != "1" ]; then
    echo "ERROR: Gemini is a legacy agent and is not allowed in this lab." >&2
    echo "Set ALLOW_LEGACY_AGENTS=1 to override." >&2
    exit 1
fi

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BINARY="$PROJECT_ROOT/tools/rust/automation-cli/target/release/automation-cli"

if [[ ! -x "$BINARY" ]]; then
    echo "ERROR: automation-cli not built. Run: cargo build --release --manifest-path tools/rust/automation-cli/Cargo.toml" >&2
    exit 1
fi

exec "$BINARY" launch gemini-mcp "$@"
