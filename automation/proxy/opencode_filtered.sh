#!/bin/bash
# OpenCode wrapper that filters model output

# Create a named pipe for filtering
PIPE="/tmp/opencode_filter_$$"
mkfifo "$PIPE"

# Function to filter OpenCode output
filter_models() {
    while IFS= read -r line; do
        # Skip lines with unwanted models
        if echo "$line" | grep -qE "openrouter/|grok|gemini|llama|qwen|cognitivecomputations|featherless|thudm|google|meta|z-ai|rekaai|tngtech|x-ai"; then
            # Skip most OpenRouter models except our 3
            if ! echo "$line" | grep -qE "claude-3.5-sonnet|claude-3-opus|gpt-4"; then
                continue
            fi
        fi
        echo "$line"
    done
}

# Start OpenCode and filter its output
opencode "$@" 2>&1 | filter_models
