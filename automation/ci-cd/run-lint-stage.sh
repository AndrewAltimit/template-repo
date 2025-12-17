#!/bin/bash
# Linting stage runner with error/warning counting
# Used by lint-stages.yml workflow

set -e

# Get the script's directory to find the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root so relative paths in docker-compose.yml work correctly
cd "$PROJECT_ROOT"

STAGE=${1:-format}

# Export user IDs for docker-compose
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# Helper function to ensure numeric value
ensure_numeric() {
  local value="${1:-0}"
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "$value"
  else
    echo 0
  fi
}

# Initialize counters
errors=0
warnings=0
baseline_failed=0

# Clear any previous lint output
rm -f lint-output.txt

# Build the CI image if needed
echo "🔨 Building CI image..."
docker-compose build python-ci

case "$STAGE" in
  format)
    echo "=== Running format check ==="

    # Check formatting with ruff (replaces black, 10-100x faster)
    echo "🔍 Checking Python formatting with ruff..."
    if ! docker-compose run --rm python-ci ruff format --check --diff . 2>&1 | tee ruff-format-output.txt; then
      errors=$((errors + $(grep -c "would reformat" ruff-format-output.txt || echo 0)))
    fi

    # Check import sorting
    echo "🔍 Checking import sorting with ruff..."
    if ! docker-compose run --rm python-ci ruff check --select=I --diff . 2>&1 | tee ruff-import-output.txt; then
      errors=$((errors + $(grep -c "I001" ruff-import-output.txt || echo 0)))
    fi
    ;;

  ruff)
    echo "=== Running Ruff (fast linter) ==="
    echo "🔍 Running Ruff check..."
    docker-compose run --rm python-ci ruff check . --output-format=grouped 2>&1 | tee ruff-output.txt || true

    # Count Ruff issues (extract total from "Found X errors" line)
    if [ -f ruff-output.txt ]; then
      ruff_errors=$(grep -oP "Found \K[0-9]+" ruff-output.txt 2>/dev/null | head -1 || echo 0)
      ruff_errors=$(ensure_numeric "$ruff_errors")
      errors=$((errors + ${ruff_errors:-0}))
    fi
    ;;

  basic)
    echo "=== Running basic linting ==="

    # Format checks (ruff format replaces black, 10-100x faster)
    echo "🔍 Checking formatting with ruff..."
    docker-compose run --rm python-ci ruff format --check . 2>&1 | tee -a lint-output.txt || true
    # Import sorting check
    docker-compose run --rm python-ci ruff check --select=I . 2>&1 | tee -a lint-output.txt || true

    # Ruff critical errors only (replaces flake8 E9,F63,F7,F82)
    echo "🔍 Running ruff (critical errors)..."
    if ! docker-compose run --rm python-ci ruff check --select=E9,F63,F7,F82 --output-format=grouped . 2>&1 | tee -a lint-output.txt; then
      # Count critical errors from ruff output
      ruff_critical=$(grep -cE "^\s+[0-9]+:" lint-output.txt 2>/dev/null || echo 0)
      ruff_critical=$(ensure_numeric "$ruff_critical")
      errors=$((errors + ${ruff_critical:-0}))
    fi

    # Ruff style check (informational, doesn't fail build)
    echo "🔍 Running ruff (style check)..."
    docker-compose run --rm python-ci ruff check --select=E,W,C90 --exit-zero --output-format=grouped . 2>&1 | tee -a lint-output.txt

    # Pylint (explicitly use pyproject.toml config for disabled warnings)
    echo "🔍 Running Pylint..."
    docker-compose run --rm python-ci bash -c 'find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" | xargs pylint --rcfile=pyproject.toml --output-format=parseable --exit-zero' 2>&1 | tee -a lint-output.txt || true

    # Count Pylint issues (informational only - baseline check determines pass/fail)
    if [ -f lint-output.txt ]; then
      pylint_errors=$(grep -cE ":[0-9]+: \[E[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      pylint_warnings=$(grep -cE ":[0-9]+: \[W[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric (for reporting only)
      pylint_errors=$(ensure_numeric "$pylint_errors")
      pylint_warnings=$(ensure_numeric "$pylint_warnings")
      # Note: Not adding to errors/warnings counts - baseline check handles this
      echo "  Pylint found $pylint_errors E-codes, $pylint_warnings W-codes (checked against baseline)"
    fi

    # Check against lint baseline to prevent regressions
    echo ""
    echo "🔍 Checking against lint baseline..."
    BASELINE_FILE="$PROJECT_ROOT/config/lint/pylint-baseline.json"
    if [ -f "$BASELINE_FILE" ] && [ -f lint-output.txt ]; then
      if docker-compose run --rm python-ci python automation/ci-cd/check-lint-baseline.py lint-output.txt --baseline config/lint/pylint-baseline.json; then
        echo "✅ Lint baseline check passed"
      else
        echo "❌ Lint baseline check failed - new warnings detected"
        baseline_failed=1
      fi
    else
      echo "⚠️  Baseline file not found, skipping regression check"
    fi
    ;;

  full)
    echo "=== Running full linting suite ==="

    # Run all basic checks but capture their output
    # Note: basic stage will exit, so we need to re-run those checks here

    # Format checks (ruff format replaces black, 10-100x faster)
    echo "🔍 Checking formatting with ruff..."
    docker-compose run --rm python-ci ruff format --check . 2>&1 | tee lint-output.txt || true
    # Import sorting check
    docker-compose run --rm python-ci ruff check --select=I . 2>&1 | tee -a lint-output.txt || true

    # Ruff - full linting (replaces flake8, 10-100x faster)
    echo "🔍 Running ruff (full linting)..."
    docker-compose run --rm python-ci ruff check --output-format=grouped . 2>&1 | tee -a lint-output.txt || true
    if [ -f lint-output.txt ]; then
      # Extract the actual error count from "Found X errors" line (informational)
      ruff_issues=$(grep -oP "Found \K[0-9]+" lint-output.txt 2>/dev/null | head -1 || echo 0)
      ruff_issues=$(ensure_numeric "$ruff_issues")
      echo "  Ruff found $ruff_issues issues (informational)"
    fi

    # Ruff critical errors only (syntax errors, undefined names, etc.)
    echo "🔍 Running ruff (critical errors)..."
    if ! docker-compose run --rm python-ci ruff check --select=E9,F63,F7,F82 --output-format=grouped . 2>&1 | tee -a lint-output.txt; then
      # Count critical errors from ruff output
      ruff_critical=$(grep -cE "^\s+[0-9]+:" lint-output.txt 2>/dev/null || echo 0)
      ruff_critical=$(ensure_numeric "$ruff_critical")
      errors=$((errors + ${ruff_critical:-0}))
    fi

    # Pylint (explicitly use pyproject.toml config for disabled warnings)
    # Note: Keep pylint as it catches issues ruff doesn't yet
    echo "🔍 Running Pylint..."
    docker-compose run --rm python-ci bash -c 'find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" | xargs pylint --rcfile=pyproject.toml --output-format=parseable --exit-zero' 2>&1 | tee -a lint-output.txt || true

    # Count Pylint issues (informational only - baseline check determines pass/fail)
    if [ -f lint-output.txt ]; then
      pylint_errors=$(grep -cE ":[0-9]+: \[E[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      pylint_warnings=$(grep -cE ":[0-9]+: \[W[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric (for reporting only)
      pylint_errors=$(ensure_numeric "$pylint_errors")
      pylint_warnings=$(ensure_numeric "$pylint_warnings")
      # Note: Not adding to errors/warnings counts - baseline check handles this
      echo "  Pylint found $pylint_errors E-codes, $pylint_warnings W-codes (checked against baseline)"
    fi

    # Type checking with MyPy (informational - doesn't fail build)
    # Using uv for fast dependency installation
    echo "🔍 Running MyPy type checker..."
    docker-compose run --rm python-ci bash -c "uv pip install --system -r config/python/requirements.txt && mypy . --ignore-missing-imports --no-error-summary" 2>&1 | tee -a lint-output.txt || true
    # Note: Not counting mypy errors as hard failures - baseline check handles regressions
    mypy_errors=$(grep -c ": error:" lint-output.txt 2>/dev/null || echo 0)
    mypy_errors=$(ensure_numeric "$mypy_errors")
    echo "  MyPy found $mypy_errors errors (informational)"

    # Security scanning with Bandit (informational)
    echo "🔍 Running Bandit security scanner..."
    docker-compose run --rm python-ci bandit -r . -c pyproject.toml -f json -o bandit-report.json 2>&1 | tee -a lint-output.txt || true
    if [ -f bandit-report.json ]; then
      bandit_issues=$(docker-compose run --rm python-ci python3 -c "import json; data=json.load(open('bandit-report.json')); print(len(data.get('results', [])))" || echo 0)
      echo "  Bandit found $bandit_issues security issues (informational)"
    fi

    # Dependency security check - try Safety first, fallback to pip-audit
    echo "🔍 Checking dependency security..."
    if [ -f config/python/requirements.txt ]; then
      # Check if SAFETY_API_KEY is available
      if [ -n "$SAFETY_API_KEY" ]; then
        echo "Using Safety with API key..."
        # Use safety scan with API key
        safety_output=$(docker-compose run --rm -T -e SAFETY_API_KEY="$SAFETY_API_KEY" python-ci safety scan --key "$SAFETY_API_KEY" --disable-optional-telemetry --output json 2>&1 || true)
        echo "$safety_output" | tee -a lint-output.txt
        # Parse the new JSON format from safety scan
        if [[ "$safety_output" == *"{"* ]] && [[ "$safety_output" != *"Unhandled exception"* ]]; then
          # Valid JSON output, count vulnerabilities from the new format
          safety_issues=$(echo "$safety_output" | docker-compose run --rm python-ci python3 -c "import sys, json; data=json.load(sys.stdin); vulns=data.get('vulnerabilities', []); print(len(vulns))" 2>/dev/null || echo 0)
          # Ensure safety_issues is a valid number
          if [[ "$safety_issues" =~ ^[0-9]+$ ]]; then
            warnings=$((warnings + safety_issues))
          fi
        fi
      else
        echo "No SAFETY_API_KEY found, using pip-audit instead..."
        # Use pip-audit as fallback (run as module since it's in user directory)
        pip_audit_output=$(docker-compose run --rm -T python-ci python -m pip_audit --format json 2>&1 || true)
        echo "$pip_audit_output" | tee -a lint-output.txt
        # Parse pip-audit JSON output
        if [[ "$pip_audit_output" == *"{"* ]]; then
          audit_issues=$(echo "$pip_audit_output" | docker-compose run --rm python-ci python3 -c "import sys, json; data=json.load(sys.stdin); vulns=data.get('vulnerabilities', []); print(len(vulns))" 2>/dev/null || echo 0)
          # Ensure audit_issues is a valid number
          if [[ "$audit_issues" =~ ^[0-9]+$ ]]; then
            warnings=$((warnings + audit_issues))
          fi
        fi
      fi
    fi

    # Report total issues from lint-output.txt (informational only)
    # Baseline check determines pass/fail, not these counts
    if [ -f lint-output.txt ]; then
      total_errors=$(grep -cE "(error:|ERROR:|Error:)" lint-output.txt 2>/dev/null || echo 0)
      total_warnings=$(grep -cE "(warning:|WARNING:|Warning:)" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric
      total_errors=$(ensure_numeric "$total_errors")
      total_warnings=$(ensure_numeric "$total_warnings")
      echo "  Total error/warning strings in output: $total_errors errors, $total_warnings warnings (informational)"
    fi

    # Check against lint baseline to prevent regressions
    echo ""
    echo "🔍 Checking against lint baseline..."
    BASELINE_FILE="$PROJECT_ROOT/config/lint/pylint-baseline.json"
    if [ -f "$BASELINE_FILE" ] && [ -f lint-output.txt ]; then
      if docker-compose run --rm python-ci python automation/ci-cd/check-lint-baseline.py lint-output.txt --baseline config/lint/pylint-baseline.json; then
        echo "✅ Lint baseline check passed"
      else
        echo "❌ Lint baseline check failed - new warnings detected"
        # Set baseline_failed flag for exit handling
        baseline_failed=1
      fi
    else
      echo "⚠️  Baseline file not found, skipping regression check"
    fi
    ;;

  links)
    echo "=== Running markdown link check ==="

    # Build MCP Code Quality container if needed
    echo "🔨 Building MCP Code Quality container..."
    docker build -f docker/mcp-code-quality.Dockerfile -t mcp-code-quality:latest .

    echo "🔍 Checking links in markdown files..."

    # Export user to run container as non-root
    USER_ID=$(id -u)
    GROUP_ID=$(id -g)
    export USER_ID
    export GROUP_ID

    # Build base docker command
    DOCKER_CMD="docker run --rm --user ${USER_ID}:${GROUP_ID} -v \"${GITHUB_WORKSPACE:-$(pwd)}\":/workspace -w /workspace"

    # Add GITHUB_OUTPUT mount if available
    if [ -n "${GITHUB_OUTPUT}" ]; then
      GITHUB_OUTPUT_DIR=$(dirname "${GITHUB_OUTPUT}")
      GITHUB_OUTPUT_FILE=$(basename "${GITHUB_OUTPUT}")
      DOCKER_CMD="${DOCKER_CMD} -v \"${GITHUB_OUTPUT_DIR}\":/github -e GITHUB_OUTPUT=/github/${GITHUB_OUTPUT_FILE}"
    fi

    # Run the container with link checker
    # Default to internal-only for PR checks (faster)
    eval "${DOCKER_CMD} mcp-code-quality:latest \
      python /workspace/automation/analysis/check-markdown-links.py \
        /workspace \
        --format github \
        --output /workspace/link_check_summary.md \
        --internal-only" 2>&1 | tee lint-output.txt

    # Check if link check failed
    if [ "${PIPESTATUS[0]}" -ne 0 ]; then
      errors=$((errors + 1))
    fi

    # Count broken links from the output
    if [ -f link_check_summary.md ]; then
      broken_links=$(grep -oP 'Broken links: \K\d+' link_check_summary.md || echo 0)
      errors=$((errors + broken_links))
    fi
    ;;

  *)
    echo "Invalid stage: $STAGE"
    echo "Available stages: format, ruff, basic, full, links"
    exit 1
    ;;
esac

# Export results for GitHub Actions (if running in GitHub Actions)
if [ -n "$GITHUB_ENV" ]; then
  echo "errors=$errors" >> "$GITHUB_ENV"
  echo "warnings=$warnings" >> "$GITHUB_ENV"
fi

# Summary
echo ""
echo "=== Linting Summary ==="
echo "Errors: $errors"
echo "Warnings: $warnings"

# Exit with error code if issues found
if [[ $errors -gt 0 ]]; then
  echo "❌ Linting failed with $errors errors"
  exit 1
elif [[ $baseline_failed -eq 1 ]]; then
  echo "❌ Lint baseline check failed - new warnings introduced"
  exit 1
else
  echo "✅ Linting completed"
fi
