#!/bin/bash
# Test script for security hooks and secret masking
# Tests both the YAML configuration and masking functionality

# Shell hardening: exit on error, undefined variables, and pipe failures
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Testing Security Hooks with .secrets.yaml Configuration"
echo "========================================================"
echo

# Set up test environment variables from our config
export GITHUB_TOKEN="ghp_test1234567890abcdefghijklmnopqrstuv"
export AI_AGENT_TOKEN="ai_agent_secret_token_12345"
export OPENROUTER_API_KEY="sk-or-v1-testkey1234567890abcdefghijklmnop"
export DB_PASSWORD="database_password_123"
export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
export STRIPE_SECRET_KEY="sk_test_fake123456789012345678901234"
export JWT_SECRET="jwt_secret_token_for_testing"
export WEBHOOK_URL="https://hooks.example.com/secret-webhook-url"

# Test auto-detection patterns
export MY_CUSTOM_TOKEN="custom_token_value_789"
export SOMETHING_SECRET="auto_detected_secret"
export PRIVATE_DATA="private_data_value"
export PUBLIC_KEY="this_should_not_be_masked"  # Excluded pattern

echo "=== Test 1: GitHub Token Masking ==="
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token is ghp_test1234567890abcdefghijklmnopqrstuv\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
result=$(echo "$json_output" | jq -r '.tool_input.command')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
if [[ "$result" == *"[MASKED_GITHUB_TOKEN]"* ]] && [[ "$permission" == "allow_with_modifications" ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 2: Multiple Secrets ==="
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh issue comment 1 --body \"API: sk-or-v1-testkey1234567890abcdefghijklmnop DB: database_password_123\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
result=$(echo "$json_output" | jq -r '.tool_input.command')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
if [[ "$result" == *"[MASKED_OPENROUTER_API_KEY]"* ]] && [[ "$result" == *"[MASKED_DB_PASSWORD]"* ]] && [[ "$permission" == "allow_with_modifications" ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 3: Auto-Detection (*_TOKEN, *_SECRET) ==="
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token: custom_token_value_789 Secret: auto_detected_secret\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
result=$(echo "$json_output" | jq -r '.tool_input.command')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
if [[ "$result" == *"[MASKED_MY_CUSTOM_TOKEN]"* ]] && [[ "$result" == *"[MASKED_SOMETHING_SECRET]"* ]] && [[ "$permission" == "allow_with_modifications" ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 4: Excluded Pattern (PUBLIC_KEY) ==="
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Key: this_should_not_be_masked\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
# When no modifications, tool_input is not included in response
result=$(echo "$json_output" | jq -r '.tool_input.command // "not_modified"')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
# Check that no modifications were made (result is "not_modified") and permission is "allow"
if [[ "$result" == "not_modified" ]] && [[ "$permission" == "allow" ]]; then
    echo "✓ PASSED - PUBLIC_KEY not masked, permission=allow"
else
    echo "✗ FAILED - PUBLIC_KEY was masked or wrong permission"
fi
echo

echo "=== Test 5: Pattern Detection (AWS, Stripe, JWT) ==="
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create --body \"AWS: AKIAIOSFODNN7EXAMPLE Stripe: sk_test_fake123456789012345678901234\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
result=$(echo "$json_output" | jq -r '.tool_input.command')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
if [[ "$result" == *"[MASKED_AWS_ACCESS_KEY"* ]] && [[ "$result" == *"[MASKED_STRIPE"* ]] && [[ "$permission" == "allow_with_modifications" ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 6: Non-GitHub Command (Should Pass Through) ==="
# shellcheck disable=SC2016
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"echo $GITHUB_TOKEN $DB_PASSWORD"}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
# When no modifications, tool_input is not included in response
result=$(echo "$json_output" | jq -r '.tool_input.command // "not_modified"')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
# Check that no modifications were made (result is "not_modified") and permission is "allow"
if [[ "$result" == "not_modified" ]] && [[ "$permission" == "allow" ]]; then
    echo "✓ PASSED - Non-gh command unchanged, permission=allow"
else
    echo "✗ FAILED - Non-gh command was modified or wrong permission"
fi
echo

echo "=== Test 7: Full Hook Pipeline ==="
echo "Testing complete bash-pretooluse-hook.sh pipeline..."
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token ghp_test1234567890abcdefghijklmnopqrstuv\""}}' | bash "${SCRIPT_DIR}/bash-pretooluse-hook.sh" 2>/dev/null)
permission=$(echo "$result" | jq -r '.permissionDecision' 2>/dev/null)
if [[ "$permission" == "allow" ]] || [[ "$permission" == "deny" ]]; then
    echo "✓ PASSED - Hook pipeline working"
else
    echo "✗ FAILED - Hook pipeline error"
    echo "Result: $result"
fi
echo

echo "=== Test 8: URL with Embedded Credentials ==="
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh issue comment 1 --body \"URL: https://user:password123@example.com/api\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
result=$(echo "$json_output" | jq -r '.tool_input.command')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
if [[ "$result" == *"[MASKED_URL_WITH_AUTH]"* ]] && [[ "$permission" == "allow_with_modifications" ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 9: Bearer Token ==="
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
result=$(echo "$json_output" | jq -r '.tool_input.command')
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Result: $result"
echo "Permission: $permission"
if [[ "$result" == *"[MASKED_BEARER_TOKEN]"* ]] && [[ "$permission" == "allow_with_modifications" ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 10: Configuration Loading ==="
echo -n "Checking if .secrets.yaml is loaded... "
output=$(echo '{"tool_name":"Bash","tool_input":{"command":"test"}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>&1 1>/dev/null || true)
if [[ "$output" == *"ERROR: No configuration file found"* ]]; then
    echo "✗ ERROR - Would block commands (fail-closed)"
else
    echo "✓ Config loaded successfully"
fi
echo

echo "=== Test 11: Hook Fallback Scenario (No Validator) ==="
echo "Testing behavior when gh-comment-validator.py is not present..."

# Temporarily rename validator files if they exist
VALIDATOR_RENAMED=false
CLAUDE_VALIDATOR_RENAMED=false

if [ -f "${SCRIPT_DIR}/gh-comment-validator.py" ]; then
    mv "${SCRIPT_DIR}/gh-comment-validator.py" "${SCRIPT_DIR}/gh-comment-validator.py.bak"
    VALIDATOR_RENAMED=true
fi

if [ -f "${SCRIPT_DIR}/../claude-hooks/gh-comment-validator.py" ]; then
    mv "${SCRIPT_DIR}/../claude-hooks/gh-comment-validator.py" "${SCRIPT_DIR}/../claude-hooks/gh-comment-validator.py.bak"
    CLAUDE_VALIDATOR_RENAMED=true
fi

# Test that secrets are still masked even without validator
test_input='{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token is ghp_test1234567890abcdefghijklmnopqrstuv\""}}'
result=$(echo "$test_input" | "${SCRIPT_DIR}/bash-pretooluse-hook.sh" 2>/dev/null || true)

# Check if the result contains proper permission decision and masked token
if echo "$result" | jq -e '.permissionDecision' >/dev/null 2>&1; then
    permission=$(echo "$result" | jq -r '.permissionDecision')
    if [[ "$permission" == "allow_with_modifications" ]]; then
        command=$(echo "$result" | jq -r '.tool_input.command')
        if [[ "$command" == *"[MASKED_GITHUB_TOKEN]"* ]]; then
            echo "✓ PASSED - Secrets masked even without validator"
        else
            echo "✗ FAILED - Secrets not masked in fallback scenario!"
            echo "  Command: $command"
        fi
    else
        echo "✗ FAILED - Wrong permission decision: $permission"
    fi
else
    echo "✗ FAILED - Invalid JSON response in fallback scenario"
    echo "  Response: $result"
fi

# Restore validator files
if [ "$VALIDATOR_RENAMED" = true ]; then
    mv "${SCRIPT_DIR}/gh-comment-validator.py.bak" "${SCRIPT_DIR}/gh-comment-validator.py"
fi

if [ "$CLAUDE_VALIDATOR_RENAMED" = true ]; then
    mv "${SCRIPT_DIR}/../claude-hooks/gh-comment-validator.py.bak" "${SCRIPT_DIR}/../claude-hooks/gh-comment-validator.py"
fi

echo

echo "=== Test 12: Stdin Security Bypass Protection ==="
echo "Testing that --body-file - commands are blocked..."
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"echo \"Token ghp_test1234567890abcdefghijklmnopqrstuv\" | gh pr comment 123 --body-file -"}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
permission=$(echo "$json_output" | jq -r '.permissionDecision')
reason=$(echo "$json_output" | jq -r '.reason // ""')
echo "Permission: $permission"
echo "Reason: $reason"
if [[ "$permission" == "block" ]] && [[ "$reason" == *"stdin"* ]]; then
    echo "✓ PASSED - stdin commands blocked for security"
else
    echo "✗ FAILED - stdin commands not blocked!"
fi
echo

echo "=== Test 13: Stdin with Equals Sign Also Blocked ==="
echo "Testing that --body-file=- format is also blocked..."
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 123 --body-file=-"}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Permission: $permission"
if [[ "$permission" == "block" ]]; then
    echo "✓ PASSED - --body-file=- format blocked"
else
    echo "✗ FAILED - --body-file=- format not blocked!"
fi
echo

echo "=== Test 14: Regular --body-file with Filename Allowed ==="
echo "Testing that --body-file with actual filename is still allowed..."
json_output=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 123 --body-file /tmp/comment.md"}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null)
permission=$(echo "$json_output" | jq -r '.permissionDecision')
echo "Permission: $permission"
if [[ "$permission" == "allow" ]]; then
    echo "✓ PASSED - regular file usage allowed"
else
    echo "✗ FAILED - regular file usage blocked incorrectly"
fi
echo

echo "=== Test 15: Fail-Closed Behavior (No Config File) ==="
echo "Testing behavior when .secrets.yaml is not found..."

# Temporarily rename config file to test fail-closed behavior
CONFIG_RENAMED=false
if [ -f "${SCRIPT_DIR}/../../.secrets.yaml" ]; then
    mv "${SCRIPT_DIR}/../../.secrets.yaml" "${SCRIPT_DIR}/../../.secrets.yaml.bak"
    CONFIG_RENAMED=true
fi

# Test that commands are blocked when config is missing
test_input='{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"This should be blocked\""}}'
result=$(echo "$test_input" | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null || true)

# Check if the command was blocked
if echo "$result" | jq -e '.permissionDecision' >/dev/null 2>&1; then
    permission=$(echo "$result" | jq -r '.permissionDecision')
    if [[ "$permission" == "block" ]]; then
        reason=$(echo "$result" | jq -r '.reason // ""')
        if [[ "$reason" == *"failing closed for security"* ]]; then
            echo "✓ PASSED - Commands blocked when config missing (fail-closed)"
        else
            echo "✗ FAILED - Wrong block reason: $reason"
        fi
    else
        echo "✗ FAILED - Command not blocked: $permission"
    fi
else
    echo "✗ FAILED - Invalid response when config missing"
fi

# Restore config file
if [ "$CONFIG_RENAMED" = true ]; then
    mv "${SCRIPT_DIR}/../../.secrets.yaml.bak" "${SCRIPT_DIR}/../../.secrets.yaml"
fi

echo

echo "========================================================"
echo "Testing complete!"
echo
echo "Configuration file: ${SCRIPT_DIR}/../../.secrets.yaml"
echo "To add new secrets, edit .secrets.yaml in repository root"
