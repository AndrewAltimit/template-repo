#!/bin/bash
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
# The wrapper passes the command through validation hooks before execution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_GH="/usr/bin/gh"  # Path to actual gh binary

# Check if this is a comment/create command that needs validation
needs_validation() {
    local cmd="$*"
    if [[ "$cmd" =~ (pr|issue)[[:space:]]+(comment|create) ]]; then
        return 0
    fi
    return 1
}

# Validate command using Python validators
validate_command() {
    local cmd="$*"

    # Create a JSON input similar to what Claude Code hooks expect
    local json_input
    json_input=$(cat <<EOF
{
    "tool_name": "Bash",
    "tool_input": {
        "command": "gh $cmd"
    }
}
EOF
)

    # Run through the secret masker
    local masked_output
    masked_output=$(echo "$json_input" | python3 "${SCRIPT_DIR}/github-secrets-masker.py")
    local permission
    permission=$(echo "$masked_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecision', 'allow'))" 2>/dev/null || echo "allow")

    if [[ "$permission" == "deny" ]]; then
        local reason
        reason=$(echo "$masked_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecisionReason', 'Command blocked'))" 2>/dev/null || echo "Command blocked")
        echo "ERROR: Command blocked by security validation" >&2
        echo "$reason" >&2
        return 1
    fi

    # Extract potentially modified command
    local modified_cmd
    modified_cmd=$(echo "$masked_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('modifiedCommand', ''))" 2>/dev/null || echo "")

    # If command was modified (secrets masked), use the modified version
    if [[ -n "$modified_cmd" && "$modified_cmd" != "gh $cmd" ]]; then
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
        local validator_output
        validator_output=$(echo "$json_input" | python3 "${SCRIPT_DIR}/gh-comment-validator.py")
        permission=$(echo "$validator_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecision', 'allow'))" 2>/dev/null || echo "allow")

        if [[ "$permission" == "deny" ]]; then
            local reason
            reason=$(echo "$validator_output" | python3 -c "import json, sys; data = json.loads(sys.stdin.read()); print(data.get('permissionDecisionReason', 'Command blocked'))" 2>/dev/null || echo "Command blocked")
            echo "ERROR: Command blocked by comment validator" >&2
            echo "$reason" >&2
            return 1
        fi
    fi

    # Return the potentially modified command
    echo "$cmd"
}

# Main execution
main() {
    local original_cmd="$*"

    # Check if validation is needed
    if needs_validation "$original_cmd"; then
        # Validate and potentially modify the command
        local validated_cmd
        validated_cmd=$(validate_command "$original_cmd")
        local validation_result=$?

        if [[ $validation_result -ne 0 ]]; then
            # Validation failed, exit with error
            exit 1
        fi

        # Execute the validated/modified command
        # shellcheck disable=SC2086
        exec "$REAL_GH" $validated_cmd
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
