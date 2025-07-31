#!/bin/bash
# CGT Validator CLI wrapper script
# Sets up PYTHONPATH to ensure proper imports

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set PYTHONPATH to include src directory
export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}"

# Execute the cgt-validate command with all arguments
exec cgt-validate "$@"
