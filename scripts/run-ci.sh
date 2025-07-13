#!/bin/bash
# CI/CD Helper Script for running Python tools in Docker
# This simplifies repetitive docker-compose commands in workflows

set -e

# Default to format stage if not specified
STAGE=${1:-format}
EXTRA_ARGS="${@:2}"

# Export user IDs for docker-compose
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

# Export Python cache prevention variables
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX=/tmp/pycache

# Build the CI image if needed
echo "🔨 Building CI image..."
docker-compose build python-ci

case "$STAGE" in
  format)
    echo "=== Running format checks ==="
    docker-compose run --rm python-ci black --check --diff .
    docker-compose run --rm python-ci isort --check-only --diff .
    ;;

  lint-basic)
    echo "=== Running basic linting ==="
    docker-compose run --rm python-ci black --check .
    docker-compose run --rm python-ci isort --check-only .
    docker-compose run --rm python-ci flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    docker-compose run --rm python-ci flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
    ;;

  lint-full)
    echo "=== Running full linting suite ==="
    docker-compose run --rm python-ci black --check .
    docker-compose run --rm python-ci isort --check-only .
    docker-compose run --rm python-ci flake8 . --count --statistics
    docker-compose run --rm python-ci bash -c 'find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" | xargs pylint --output-format=parseable --exit-zero'
    docker-compose run --rm python-ci bash -c "pip install -r requirements.txt && mypy . --ignore-missing-imports --no-error-summary" || true
    ;;

  security)
    echo "=== Running security scans ==="
    docker-compose run --rm python-ci bandit -r . -f json -o bandit-report.json || true
    docker-compose run --rm python-ci safety check --json --output safety-report.json || true
    ;;

  test)
    echo "=== Running tests ==="
    docker-compose run --rm \
      -e PYTHONDONTWRITEBYTECODE=1 \
      -e PYTHONPYCACHEPREFIX=/tmp/pycache \
      python-ci bash -c "pip install -r requirements.txt && pytest tests/ -v --cov=. --cov-report=xml --cov-report=term $EXTRA_ARGS"
    ;;

  yaml-lint)
    echo "=== Validating YAML files ==="
    docker-compose run --rm python-ci bash -c '
      for file in $(find . -name "*.yml" -o -name "*.yaml"); do
        echo "Checking $file..."
        yamllint "$file" || true
        python3 -c "import yaml; yaml.safe_load(open(\"$file\")); print(\"✅ Valid YAML: $file\")" || echo "❌ Invalid YAML: $file"
      done
    '
    ;;

  json-lint)
    echo "=== Validating JSON files ==="
    docker-compose run --rm python-ci bash -c '
      for file in $(find . -name "*.json"); do
        echo "Checking $file..."
        python3 -m json.tool "$file" > /dev/null && echo "✅ Valid JSON: $file" || echo "❌ Invalid JSON: $file"
      done
    '
    ;;

  autoformat)
    echo "=== Running autoformatters ==="
    docker-compose run --rm python-ci black .
    docker-compose run --rm python-ci isort .
    ;;

  *)
    echo "Unknown stage: $STAGE"
    echo "Available stages: format, lint-basic, lint-full, security, test, yaml-lint, json-lint, autoformat"
    exit 1
    ;;
esac
