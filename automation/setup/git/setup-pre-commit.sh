#!/bin/bash
# DEPRECATED: .pre-commit-config.yaml was removed in PR #292.
# This project now uses automation-cli for all CI checks.
#
# To run formatting/linting:
#   automation-cli ci run format
#   automation-cli ci run lint-full
#   automation-cli ci run full
#
# The pre-push hook in automation/setup/git/ handles pre-push validation.

set -e

echo "NOTE: pre-commit is no longer used in this project."
echo ""
echo "Code quality checks are now handled by automation-cli:"
echo "  automation-cli ci run format      # Check formatting"
echo "  automation-cli ci run lint-full   # Full linting"
echo "  automation-cli ci run full        # All checks"
echo ""
echo "See CLAUDE.md for the complete command reference."
