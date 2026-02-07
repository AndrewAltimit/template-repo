#!/bin/bash
# Thin wrapper: delegates to automation-cli Rust binary
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BINARY="$PROJECT_ROOT/tools/rust/automation-cli/target/release/automation-cli"

if [[ ! -x "$BINARY" ]]; then
    echo "ERROR: automation-cli not built. Run: cargo build --release -p automation-cli" >&2
    exit 1
fi

exec "$BINARY" wait "$@"
