#!/bin/bash
# Setup a git alias for auto-formatting commits

echo "Setting up 'git cf' (commit with auto-format) alias..."

git config alias.cf '!f() {
    # Run pre-commit and capture the result
    if pre-commit run; then
        # All good, proceed with commit
        git commit "$@"
    else
        # Check if files were modified
        if ! git diff --quiet; then
            echo "Files were reformatted. Auto-staging and retrying..."
            git add -u
            if pre-commit run; then
                git commit "$@"
            else
                echo "Pre-commit checks still failing after formatting."
                exit 1
            fi
        else
            echo "Pre-commit checks failed (not due to formatting)."
            exit 1
        fi
    fi
}; f'

echo "✅ Git alias 'cf' has been set up!"
echo ""
echo "Usage:"
echo "  git cf -m 'Your commit message'    # Commit with auto-formatting"
echo "  git commit -m 'Message'            # Regular commit (manual staging)"
echo ""
echo "The 'cf' alias will:"
echo "  1. Run formatters"
echo "  2. Auto-stage formatting changes"
echo "  3. Retry the commit"
echo ""
echo "To remove: git config --unset alias.cf"
