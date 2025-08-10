#!/bin/bash
# Test script for security hooks and secret masking
# Tests both the YAML configuration and masking functionality

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
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token is ghp_test1234567890abcdefghijklmnopqrstuv\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == *"[MASKED_GITHUB_TOKEN]"* ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 2: Multiple Secrets ==="
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh issue comment 1 --body \"API: sk-or-v1-testkey1234567890abcdefghijklmnop DB: database_password_123\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == *"[MASKED_OPENROUTER_API_KEY]"* ]] && [[ "$result" == *"[MASKED_DB_PASSWORD]"* ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 3: Auto-Detection (*_TOKEN, *_SECRET) ==="
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Token: custom_token_value_789 Secret: auto_detected_secret\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == *"[MASKED_MY_CUSTOM_TOKEN]"* ]] && [[ "$result" == *"[MASKED_SOMETHING_SECRET]"* ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 4: Excluded Pattern (PUBLIC_KEY) ==="
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Key: this_should_not_be_masked\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == *"this_should_not_be_masked"* ]] && [[ "$result" != *"[MASKED"* ]]; then
    echo "✓ PASSED - PUBLIC_KEY not masked"
else
    echo "✗ FAILED - PUBLIC_KEY was masked"
fi
echo

echo "=== Test 5: Pattern Detection (AWS, Stripe, JWT) ==="
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr create --body \"AWS: AKIAIOSFODNN7EXAMPLE Stripe: sk_test_fake123456789012345678901234\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == *"[MASKED_AWS_ACCESS_KEY"* ]] && [[ "$result" == *"[MASKED_STRIPE"* ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 6: Non-GitHub Command (Should Pass Through) ==="
# shellcheck disable=SC2016
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"echo $GITHUB_TOKEN $DB_PASSWORD"}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == "echo \$GITHUB_TOKEN \$DB_PASSWORD" ]]; then
    echo "✓ PASSED - Non-gh command unchanged"
else
    echo "✗ FAILED - Non-gh command was modified"
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
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh issue comment 1 --body \"URL: https://user:password123@example.com/api\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == *"[MASKED_URL_WITH_AUTH]"* ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 9: Bearer Token ==="
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"gh pr comment 1 --body \"Auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\""}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>/dev/null | jq -r '.tool_input.command')
echo "Result: $result"
if [[ "$result" == *"[MASKED_BEARER_TOKEN]"* ]]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi
echo

echo "=== Test 10: Configuration Loading ==="
echo -n "Checking if .secrets.yaml is loaded... "
output=$(echo '{"tool_name":"Bash","tool_input":{"command":"test"}}' | python3 "${SCRIPT_DIR}/github-secrets-masker.py" 2>&1 1>/dev/null)
if [[ "$output" == *"Warning: No config file found"* ]]; then
    echo "✗ WARNING - Using fallback config"
else
    echo "✓ Config loaded successfully"
fi
echo

echo "========================================================"
echo "Testing complete!"
echo
echo "Configuration file: ${SCRIPT_DIR}/../../.secrets.yaml"
echo "To add new secrets, edit .secrets.yaml in repository root"
