#!/usr/bin/env bash
# Pre-commit hook: run cargo fmt on all standalone MCP servers
# Skips mcp_core_rust, mcp_bioforge, mcp_code_quality (have dedicated hooks)
set -euo pipefail
# shellcheck source=/dev/null
source "$HOME/.cargo/env" 2>/dev/null || true

for dir in tools/mcp/*/; do
    name=$(basename "$dir")
    case "$name" in
        mcp_core_rust|mcp_bioforge|mcp_code_quality) continue ;;
    esac
    if [ -f "$dir/Cargo.toml" ]; then
        (cd "$dir" && cargo fmt --all)
    fi
done
