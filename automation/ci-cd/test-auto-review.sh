#!/bin/bash
# Test script for auto-review functionality using Rust CLI

echo "=== Auto Review Test Script ==="
echo "This script tests the auto-review functionality locally using the Rust CLI"
echo ""

# Set up environment variables
export GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')}"

# Parse command line arguments
TARGET="${1:-both}"

echo "Configuration:"
echo "  Repository: $GITHUB_REPOSITORY"
echo "  Target: $TARGET"
echo ""

# Find the github-agents binary
GITHUB_AGENTS=""
SEARCH_PATHS=(
    "./tools/rust/github-agents-cli/target/release/github-agents"
    "$HOME/.local/bin/github-agents"
)

for path in "${SEARCH_PATHS[@]}"; do
    if [ -x "$path" ]; then
        GITHUB_AGENTS="$path"
        break
    fi
done

# Try PATH lookup if not found
if [ -z "$GITHUB_AGENTS" ]; then
    GITHUB_AGENTS=$(command -v github-agents 2>/dev/null || true)
fi

if [ -z "$GITHUB_AGENTS" ]; then
    echo "❌ github-agents binary not found. Please build it first:"
    echo "   cd tools/rust/github-agents-cli && cargo build --release"
    exit 1
fi

echo "Using github-agents at: $GITHUB_AGENTS"
echo ""

# Run the review
echo "Starting auto-review..."
echo ""

SUCCESS=true

if [ "$TARGET" = "issues" ] || [ "$TARGET" = "both" ]; then
    echo "=== Processing Issues ==="
    "$GITHUB_AGENTS" issue-monitor || {
        echo "Issue monitor returned non-zero exit code"
        SUCCESS=false
    }
    echo ""
fi

if [ "$TARGET" = "pull-requests" ] || [ "$TARGET" = "both" ]; then
    echo "=== Processing PRs ==="
    "$GITHUB_AGENTS" pr-monitor || {
        echo "PR monitor returned non-zero exit code"
        SUCCESS=false
    }
    echo ""
fi

echo "=== Auto Review Complete ==="
if [ "$SUCCESS" = "true" ]; then
    echo "All monitors completed successfully"
else
    echo "Some monitors failed - check output above"
    exit 1
fi
