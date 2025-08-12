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

# Clear any previous lint output
rm -f lint-output.txt

# Build the CI image if needed
echo "🔨 Building CI image..."
docker-compose build python-ci

case "$STAGE" in
  format)
    echo "=== Running format check ==="

    # Check Black formatting
    echo "🔍 Checking Python formatting with Black..."
    if ! docker-compose run --rm python-ci black --check --diff . 2>&1 | tee black-output.txt; then
      errors=$((errors + $(grep -c "would reformat" black-output.txt || echo 0)))
    fi

    # Check import sorting
    echo "🔍 Checking import sorting with isort..."
    if ! docker-compose run --rm python-ci isort --check-only --diff . 2>&1 | tee isort-output.txt; then
      errors=$((errors + $(grep -c "Fixing" isort-output.txt || echo 0)))
    fi
    ;;

  basic)
    echo "=== Running basic linting ==="

    # Format checks
    echo "🔍 Checking formatting..."
    docker-compose run --rm python-ci black --check . 2>&1 | tee -a lint-output.txt || true
    docker-compose run --rm python-ci isort --check-only . 2>&1 | tee -a lint-output.txt || true

    # Flake8 linting
    echo "🔍 Running Flake8..."
    docker-compose run --rm python-ci flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1 | tee -a lint-output.txt || errors=$((errors + 1))
    docker-compose run --rm python-ci flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics 2>&1 | tee -a lint-output.txt

    # Count Flake8 issues
    if [ -f lint-output.txt ]; then
      flake8_errors=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: [EF][0-9]+" lint-output.txt 2>/dev/null || echo 0)
      flake8_warnings=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: [WC][0-9]+" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric
      flake8_errors=$(ensure_numeric "$flake8_errors")
      flake8_warnings=$(ensure_numeric "$flake8_warnings")
      errors=$((errors + ${flake8_errors:-0}))
      warnings=$((warnings + ${flake8_warnings:-0}))
    fi

    # Pylint
    echo "🔍 Running Pylint..."
    docker-compose run --rm python-ci bash -c 'find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" | xargs pylint --output-format=parseable --exit-zero' 2>&1 | tee -a lint-output.txt || true

    # Count Pylint issues
    if [ -f lint-output.txt ]; then
      pylint_errors=$(grep -cE ":[0-9]+: \[E[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      pylint_warnings=$(grep -cE ":[0-9]+: \[W[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric
      pylint_errors=$(ensure_numeric "$pylint_errors")
      pylint_warnings=$(ensure_numeric "$pylint_warnings")
      errors=$((errors + ${pylint_errors:-0}))
      warnings=$((warnings + ${pylint_warnings:-0}))
    fi
    ;;

  full)
    echo "=== Running full linting suite ==="

    # Run all basic checks but capture their output
    # Note: basic stage will exit, so we need to re-run those checks here
    # or extract the values from its output

    # Format checks
    echo "🔍 Checking formatting..."
    docker-compose run --rm python-ci black --check . 2>&1 | tee lint-output.txt || true
    docker-compose run --rm python-ci isort --check-only . 2>&1 | tee -a lint-output.txt || true

    # Flake8 linting
    echo "🔍 Running Flake8..."
    docker-compose run --rm python-ci flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1 | tee -a lint-output.txt || errors=$((errors + 1))
    docker-compose run --rm python-ci flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics 2>&1 | tee -a lint-output.txt

    # Count Flake8 issues
    if [ -f lint-output.txt ]; then
      flake8_errors=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: [EF][0-9]+" lint-output.txt 2>/dev/null || echo 0)
      flake8_warnings=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: [WC][0-9]+" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric
      flake8_errors=$(ensure_numeric "$flake8_errors")
      flake8_warnings=$(ensure_numeric "$flake8_warnings")
      errors=$((errors + ${flake8_errors:-0}))
      warnings=$((warnings + ${flake8_warnings:-0}))
    fi

    # Pylint
    echo "🔍 Running Pylint..."
    docker-compose run --rm python-ci bash -c 'find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" | xargs pylint --output-format=parseable --exit-zero' 2>&1 | tee -a lint-output.txt || true

    # Count Pylint issues
    if [ -f lint-output.txt ]; then
      pylint_errors=$(grep -cE ":[0-9]+: \[E[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      pylint_warnings=$(grep -cE ":[0-9]+: \[W[0-9]+.*\]" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric
      pylint_errors=$(ensure_numeric "$pylint_errors")
      pylint_warnings=$(ensure_numeric "$pylint_warnings")
      errors=$((errors + ${pylint_errors:-0}))
      warnings=$((warnings + ${pylint_warnings:-0}))
    fi

    # Type checking with MyPy
    echo "🔍 Running MyPy type checker..."
    docker-compose run --rm python-ci bash -c "pip install -r requirements.txt && mypy . --ignore-missing-imports --no-error-summary" 2>&1 | tee -a lint-output.txt || true
    mypy_errors=$(grep -c "error:" lint-output.txt 2>/dev/null || echo 0)
    # Ensure value is numeric
    mypy_errors=$(ensure_numeric "$mypy_errors")
    errors=$((errors + ${mypy_errors:-0}))

    # Security scanning with Bandit
    echo "🔍 Running Bandit security scanner..."
    docker-compose run --rm python-ci bandit -r . -f json -o bandit-report.json 2>&1 | tee -a lint-output.txt || true
    if [ -f bandit-report.json ]; then
      bandit_issues=$(docker-compose run --rm python-ci python3 -c "import json; data=json.load(open('bandit-report.json')); print(len(data.get('results', [])))" || echo 0)
      warnings=$((warnings + bandit_issues))
    fi

    # Dependency security check - try Safety first, fallback to pip-audit
    echo "🔍 Checking dependency security..."
    if [ -f requirements.txt ]; then
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

    # Count all issues from lint-output.txt
    if [ -f lint-output.txt ]; then
      total_errors=$(grep -cE "(error:|ERROR:|Error:)" lint-output.txt 2>/dev/null || echo 0)
      total_warnings=$(grep -cE "(warning:|WARNING:|Warning:)" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric
      total_errors=$(ensure_numeric "$total_errors")
      total_warnings=$(ensure_numeric "$total_warnings")
    else
      total_errors=0
      total_warnings=0
    fi
    errors=$((errors + total_errors))
    warnings=$((warnings + total_warnings))
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
    echo "Available stages: format, basic, full, links"
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

# Exit with error code if issues found (except for full stage)
if [[ "$STAGE" != "full" && $errors -gt 0 ]]; then
  echo "❌ Linting failed with $errors errors"
  exit 1
else
  echo "✅ Linting completed"
fi
