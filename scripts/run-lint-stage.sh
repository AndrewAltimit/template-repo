#!/bin/bash
# Linting stage runner with error/warning counting
# Used by lint-stages.yml workflow

set -e

STAGE=${1:-format}

# Export user IDs for docker-compose
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# Initialize counters
errors=0
warnings=0

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
      flake8_errors=$(echo "$flake8_errors" | grep -E '^[0-9]+$' | head -1 || echo 0)
      flake8_warnings=$(echo "$flake8_warnings" | grep -E '^[0-9]+$' | head -1 || echo 0)
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
      pylint_errors=$(echo "$pylint_errors" | grep -E '^[0-9]+$' | head -1 || echo 0)
      pylint_warnings=$(echo "$pylint_warnings" | grep -E '^[0-9]+$' | head -1 || echo 0)
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
      flake8_errors=$(echo "$flake8_errors" | grep -E '^[0-9]+$' | head -1 || echo 0)
      flake8_warnings=$(echo "$flake8_warnings" | grep -E '^[0-9]+$' | head -1 || echo 0)
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
      pylint_errors=$(echo "$pylint_errors" | grep -E '^[0-9]+$' | head -1 || echo 0)
      pylint_warnings=$(echo "$pylint_warnings" | grep -E '^[0-9]+$' | head -1 || echo 0)
      errors=$((errors + ${pylint_errors:-0}))
      warnings=$((warnings + ${pylint_warnings:-0}))
    fi

    # Type checking with MyPy
    echo "🔍 Running MyPy type checker..."
    docker-compose run --rm python-ci bash -c "pip install -r requirements.txt && mypy . --ignore-missing-imports --no-error-summary" 2>&1 | tee -a lint-output.txt || true
    mypy_errors=$(grep -c "error:" lint-output.txt 2>/dev/null || echo 0)
    # Ensure value is numeric
    mypy_errors=$(echo "$mypy_errors" | grep -E '^[0-9]+$' | head -1 || echo 0)
    errors=$((errors + ${mypy_errors:-0}))

    # Security scanning with Bandit
    echo "🔍 Running Bandit security scanner..."
    docker-compose run --rm python-ci bandit -r . -f json -o bandit-report.json 2>&1 | tee -a lint-output.txt || true
    if [ -f bandit-report.json ]; then
      bandit_issues=$(docker-compose run --rm python-ci python3 -c "import json; data=json.load(open('bandit-report.json')); print(len(data.get('results', [])))" || echo 0)
      warnings=$((warnings + bandit_issues))
    fi

    # Dependency security check with Safety (using new scan command)
    echo "🔍 Checking dependency security..."
    if [ -f requirements.txt ]; then
      # Use the new 'safety scan' command which replaces deprecated 'safety check'
      # Use -T flag to disable TTY allocation and --disable-optional-telemetry to prevent prompts
      safety_output=$(docker-compose run --rm -T python-ci safety scan --disable-optional-telemetry --output json 2>&1 || true)
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
    fi

    # Count all issues from lint-output.txt
    if [ -f lint-output.txt ]; then
      total_errors=$(grep -cE "(error:|ERROR:|Error:)" lint-output.txt 2>/dev/null || echo 0)
      total_warnings=$(grep -cE "(warning:|WARNING:|Warning:)" lint-output.txt 2>/dev/null || echo 0)
      # Ensure values are numeric
      total_errors=$(echo "$total_errors" | grep -E '^[0-9]+$' | head -1 || echo 0)
      total_warnings=$(echo "$total_warnings" | grep -E '^[0-9]+$' | head -1 || echo 0)
    else
      total_errors=0
      total_warnings=0
    fi
    errors=$((errors + total_errors))
    warnings=$((warnings + total_warnings))
    ;;

  *)
    echo "Invalid stage: $STAGE"
    echo "Available stages: format, basic, full"
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
