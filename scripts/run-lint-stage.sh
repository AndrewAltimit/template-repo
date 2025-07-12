#!/bin/bash
# Linting stage runner with error/warning counting
# Used by lint-stages.yml workflow

set -e

STAGE=${1:-format}

# Export user IDs for docker-compose
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

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
    flake8_errors=$(grep -E "^[^:]+:[0-9]+:[0-9]+: [EF][0-9]+" lint-output.txt | wc -l || echo 0)
    flake8_warnings=$(grep -E "^[^:]+:[0-9]+:[0-9]+: [WC][0-9]+" lint-output.txt | wc -l || echo 0)
    errors=$((errors + flake8_errors))
    warnings=$((warnings + flake8_warnings))

    # Pylint
    echo "🔍 Running Pylint..."
    docker-compose run --rm python-ci bash -c 'find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" | xargs pylint --output-format=parseable --exit-zero' 2>&1 | tee -a lint-output.txt || true

    # Count Pylint issues
    pylint_errors=$(grep -E ":[0-9]+: \[E[0-9]+.*\]" lint-output.txt | wc -l || echo 0)
    pylint_warnings=$(grep -E ":[0-9]+: \[W[0-9]+.*\]" lint-output.txt | wc -l || echo 0)
    errors=$((errors + pylint_errors))
    warnings=$((warnings + pylint_warnings))
    ;;

  full)
    echo "=== Running full linting suite ==="

    # Run all basic checks
    ./scripts/run-lint-stage.sh basic

    # Type checking with MyPy
    echo "🔍 Running MyPy type checker..."
    docker-compose run --rm python-ci bash -c "pip install -r requirements.txt && mypy . --ignore-missing-imports --no-error-summary" 2>&1 | tee -a lint-output.txt || true
    mypy_errors=$(grep -c "error:" lint-output.txt || echo 0)
    errors=$((errors + mypy_errors))

    # Security scanning with Bandit
    echo "🔍 Running Bandit security scanner..."
    docker-compose run --rm python-ci bandit -r . -f json -o bandit-report.json 2>&1 | tee -a lint-output.txt || true
    if [ -f bandit-report.json ]; then
      bandit_issues=$(docker-compose run --rm python-ci python3 -c "import json; data=json.load(open('bandit-report.json')); print(len(data.get('results', [])))" || echo 0)
      warnings=$((warnings + bandit_issues))
    fi

    # Dependency security check with Safety
    echo "🔍 Checking dependency security..."
    if [ -f requirements.txt ]; then
      safety_output=$(docker-compose run --rm python-ci safety check --json 2>&1 || true)
      echo "$safety_output" | tee -a lint-output.txt
      if [[ "$safety_output" == *"["* ]]; then
        # Valid JSON output, count issues
        safety_issues=$(echo "$safety_output" | docker-compose run --rm python-ci python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data))" || echo 0)
        warnings=$((warnings + safety_issues))
      fi
    fi

    # Count all issues from lint-output.txt
    total_errors=$(grep -E "(error:|ERROR:|Error:)" lint-output.txt | wc -l || echo 0)
    total_warnings=$(grep -E "(warning:|WARNING:|Warning:)" lint-output.txt | wc -l || echo 0)
    errors=$((errors + total_errors))
    warnings=$((warnings + total_warnings))
    ;;

  *)
    echo "Invalid stage: $STAGE"
    echo "Available stages: format, basic, full"
    exit 1
    ;;
esac

# Export results for GitHub Actions
echo "errors=$errors" >> $GITHUB_ENV
echo "warnings=$warnings" >> $GITHUB_ENV

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
