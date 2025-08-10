#!/bin/bash
# Portable wrapper for Claude Code hook validator
# Resolves paths relative to the script location

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the Python validator with a relative path
exec python3 "${SCRIPT_DIR}/gh-comment-validator.py"
