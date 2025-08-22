#!/bin/bash
# OpenCode launcher with limited model display

# Clear screen for clean display
clear

cat << 'EOF'
╔════════════════════════════════════════════════════╗
║          🎭 Company Proxy Mode Active              ║
╠════════════════════════════════════════════════════╣
║ Available Models (via Company Proxy):              ║
║                                                     ║
║   1. Claude 3.5 Sonnet (default)                   ║
║      openrouter/anthropic/claude-3.5-sonnet        ║
║                                                     ║
║   2. Claude 3 Opus                                 ║
║      openrouter/anthropic/claude-3-opus            ║
║                                                     ║
║   3. GPT-4                                          ║
║      openrouter/openai/gpt-4                       ║
╠════════════════════════════════════════════════════╣
║ All requests routed through company API proxy      ║
║ Mock Mode: All responses = "Hatsune Miku"          ║
╚════════════════════════════════════════════════════╝

EOF

# Set default model
export OPENCODE_DEFAULT_MODEL="openrouter/anthropic/claude-3.5-sonnet"

# Launch OpenCode with our default model
exec opencode -m "$OPENCODE_DEFAULT_MODEL" "$@"
