#!/bin/bash
# Convenience wrapper for Gemini container script

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Execute the container script
exec "$SCRIPT_DIR/../containers/run_gemini_container.sh" "$@"
