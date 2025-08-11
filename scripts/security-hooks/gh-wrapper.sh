#!/bin/sh
# Agent-agnostic wrapper for gh CLI commands
#
# This wrapper intercepts gh commands and applies security validations
# before executing them. It can be used by any AI agent or automation tool
# via an alias: alias gh='/path/to/gh-wrapper.sh'
#
# Features:
# 1. Automatic secret masking in GitHub comments
# 2. GitHub comment formatting validation
# 3. Unicode emoji detection and prevention
#
# POSIX-compliant for maximum compatibility

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find the real 'gh' binary, avoiding the alias itself
REAL_GH=$(command -v gh)
if [ -z "$REAL_GH" ]; then
    echo "ERROR: 'gh' command not found." >&2
    exit 127
fi

# Check for Python 3 dependency (required for validators)
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: 'python3' command not found. The gh security wrapper requires Python 3." >&2
    echo "Please install Python 3 or run in a container with Python available." >&2
    exit 127
fi

# Check if this command needs validation based on arguments
needs_validation() {
    # Check if command contains arguments that accept user content
    for arg in "$@"; do
        case "$arg" in
            --body|--body-file|--notes|--notes-file|--title|--message)
                return 0
                ;;
        esac
    done
    return 1
}

# Validate command using Python validators
validate_command() {
    cmd="$*"
    temp_stderr="/tmp/gh-wrapper-stderr-$$"

    # Create a JSON input similar to what Claude Code hooks expect
    json_input=$(cat <<EOF
{
    "tool_name": "Bash",
    "tool_input": {
        "command": "gh $cmd"
    }
}
EOF
)

    # Run through the secret masker, capturing stderr
    masked_output=$(echo "$json_input" | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>"$temp_stderr")

    # Extract permission decision
    permission=$(echo "$masked_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecision', 'allow'))" 2>/dev/null || echo "allow")

    if [ "$permission" = "deny" ]; then
        reason=$(echo "$masked_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecisionReason', 'Command blocked'))" 2>/dev/null || echo "Command blocked")
        echo "ERROR: Command blocked by security validation" >&2
        echo "$reason" >&2
        # Show stderr from validator if present
        if [ -s "$temp_stderr" ]; then
            echo "Validator details:" >&2
            cat "$temp_stderr" >&2
        fi
        rm -f "$temp_stderr"
        return 1
    fi

    # Extract potentially modified command
    modified_cmd=$(echo "$masked_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('modifiedCommand', ''))" 2>/dev/null || echo "")

    # If command was modified (secrets masked), use the modified version
    if [ -n "$modified_cmd" ] && [ "$modified_cmd" != "gh $cmd" ]; then
        # Strip the 'gh ' prefix if present
        cmd="${modified_cmd#gh }"
    fi

    # Run through the comment validator if it exists
    if [ -f "${SCRIPT_DIR}/gh-comment-validator.py" ]; then
        json_input=$(cat <<EOF
{
    "tool_name": "Bash",
    "tool_input": {
        "command": "gh $cmd"
    }
}
EOF
)
        validator_output=$(echo "$json_input" | python3 "${SCRIPT_DIR}/gh-comment-validator.py" 2>"$temp_stderr")
        permission=$(echo "$validator_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecision', 'allow'))" 2>/dev/null || echo "allow")

        if [ "$permission" = "deny" ]; then
            reason=$(echo "$validator_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecisionReason', 'Command blocked'))" 2>/dev/null || echo "Command blocked")
            echo "ERROR: Command blocked by comment validator" >&2
            echo "$reason" >&2
            # Show stderr from validator if present
            if [ -s "$temp_stderr" ]; then
                echo "Validator details:" >&2
                cat "$temp_stderr" >&2
            fi
            rm -f "$temp_stderr"
            return 1
        fi
    fi

    # Clean up temp file
    rm -f "$temp_stderr"

    # Return the potentially modified command
    echo "$cmd"
}

# Main execution
main() {
    original_cmd="$*"

    # Check if validation is needed
    if needs_validation "$@"; then
        # Validate and potentially modify the command
        validated_cmd=$(validate_command "$original_cmd")
        validation_result=$?

        if [ $validation_result -ne 0 ]; then
            # Validation failed, exit with error
            exit 1
        fi

        # Execute the validated/modified command
        # Use eval to correctly handle arguments with spaces
        eval exec "\"$REAL_GH\" $validated_cmd"
    else
        # No validation needed, execute directly
        exec "$REAL_GH" "$@"
    fi
}

# Handle no arguments (show gh help)
if [ $# -eq 0 ]; then
    exec "$REAL_GH"
else
    main "$@"
fi
