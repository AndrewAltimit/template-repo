#!/bin/bash
# Crush wrapper script that bypasses Catwalk provider validation

set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Ensure cache directory exists
CRUSH_DATA_DIR="${HOME}/.local/share/crush"
CRUSH_CONFIG_DIR="${HOME}/.config/crush"
mkdir -p "${CRUSH_DATA_DIR}"
mkdir -p "${CRUSH_CONFIG_DIR}"

# Set Crush's project data directory to user's home
export CRUSH_DIR="${HOME}/.crush"
mkdir -p "${CRUSH_DIR}"

# Create fake provider cache that matches Catwalk format
# This cache tells Crush that OpenAI is a valid provider
cat > "${CRUSH_DATA_DIR}/providers.json" << 'EOF'
[
  {
    "id": "openai",
    "name": "OpenAI",
    "type": "openai",
    "description": "OpenAI API (Corporate Proxy)",
    "website": "https://openai.com",
    "requires_api_key": true,
    "api_key_env_var": "OPENAI_API_KEY",
    "base_url": "https://api.openai.com/v1",
    "default_model": "gpt-4",
    "default_large_model_id": "gpt-4",
    "default_small_model_id": "gpt-3.5-turbo",
    "models": [
      {
        "id": "gpt-4",
        "name": "gpt-4",
        "display_name": "GPT-4",
        "context_window": 8192,
        "max_output": 4096,
        "default_max_tokens": 4096,
        "supports_streaming": true,
        "supports_chat": true
      },
      {
        "id": "gpt-3.5-turbo",
        "name": "gpt-3.5-turbo",
        "display_name": "GPT-3.5 Turbo",
        "context_window": 4096,
        "max_output": 4096,
        "default_max_tokens": 4096,
        "supports_streaming": true,
        "supports_chat": true
      },
      {
        "id": "company/claude-3.5-sonnet",
        "name": "company/claude-3.5-sonnet",
        "display_name": "Claude 3.5 Sonnet (Company)",
        "context_window": 200000,
        "max_output": 4096,
        "default_max_tokens": 4096,
        "supports_streaming": true,
        "supports_chat": true
      },
      {
        "id": "company/gpt-4",
        "name": "company/gpt-4",
        "display_name": "GPT-4 (Company)",
        "context_window": 8192,
        "max_output": 4096,
        "default_max_tokens": 4096,
        "supports_streaming": true,
        "supports_chat": true
      }
    ],
    "headers": {},
    "query_params": {},
    "supported_features": [
      "chat",
      "completions",
      "streaming"
    ]
  }
]
EOF

# Set cache timestamp to current time
touch "${CRUSH_DATA_DIR}/providers.json"

# Check if config exists, if not copy from template
if [ ! -f "${CRUSH_CONFIG_DIR}/crush.json" ]; then
    if [ -f "/app/crush-config.json" ]; then
        cp /app/crush-config.json "${CRUSH_CONFIG_DIR}/crush.json"
    fi
fi

# Export OpenAI API key from environment
export OPENAI_API_KEY="${COMPANY_API_TOKEN:-test-secret-token-123}"

# Set Catwalk URL to invalid URL to force cache usage
export CATWALK_URL="http://localhost:9999"

# Only disable terminal features in non-TTY environments
if [ ! -t 0 ]; then
    export NO_COLOR=1
    export CRUSH_NO_SPINNER=1
    export CI=1
else
    # In TTY mode, ensure proper terminal settings
    export TERM="${TERM:-xterm-256color}"
fi

echo -e "${GREEN}Starting Crush with bypassed provider validation...${NC}"

# Change to workspace directory where files should be created
# This script only runs inside the container where /workspace is always mounted
cd /workspace

# Run the actual crush binary with all arguments
exec /usr/local/bin/crush-binary "$@"
