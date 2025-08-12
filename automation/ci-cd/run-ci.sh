#!/bin/bash
# CI/CD Helper Script for running Python tools in Docker
# This simplifies repetitive docker-compose commands in workflows

set -e

# Default to format stage if not specified
STAGE=${1:-format}
EXTRA_ARGS=("${@:2}")

# Get the script's directory to find the config path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

# Change to project root so relative paths in docker-compose.yml work correctly
cd "$PROJECT_ROOT"

# Export user IDs for docker-compose
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# Export Python cache prevention variables
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX=/tmp/pycache

# Build the CI image if needed
echo "🔨 Building CI image..."
docker-compose -f "$COMPOSE_FILE" build python-ci

case "$STAGE" in
  format)
    echo "=== Running format checks ==="
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci black --check --diff .
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci isort --check-only --diff .
    ;;

  lint-basic)
    echo "=== Running basic linting ==="
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci black --check .
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci isort --check-only .
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
    ;;

  lint-full)
    echo "=== Running full linting suite ==="
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci black --check .
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci isort --check-only .
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci flake8 . --count --statistics
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci bash -c 'find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" | xargs pylint --output-format=parseable --exit-zero'
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci bash -c "pip install -r config/python/requirements.txt && mypy . --ignore-missing-imports --no-error-summary" || true
    ;;

  security)
    echo "=== Running security scans ==="
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci bandit -r . -f json -o bandit-report.json || true
    # Dependency security check - try Safety with API key, fallback to pip-audit
    if [ -n "$SAFETY_API_KEY" ]; then
      echo "Using Safety with API key..."
      docker-compose -f "$COMPOSE_FILE" run --rm -T -e SAFETY_API_KEY="$SAFETY_API_KEY" python-ci safety scan --key "$SAFETY_API_KEY" --disable-optional-telemetry --output json > safety-report.json || true
    else
      echo "No SAFETY_API_KEY found, using pip-audit instead..."
      docker-compose -f "$COMPOSE_FILE" run --rm -T python-ci python -m pip_audit --format json > safety-report.json || true
    fi
    ;;

  test)
    echo "=== Running tests ==="
    docker-compose run --rm \
      -e PYTHONDONTWRITEBYTECODE=1 \
      -e PYTHONPYCACHEPREFIX=/tmp/pycache \
      python-ci bash -c "pip install -r config/python/requirements.txt && pytest tests/ -v --cov=. --cov-report=xml --cov-report=term --ignore=tests/gaea2/ ${EXTRA_ARGS[*]}"
    ;;

  yaml-lint)
    echo "=== Validating YAML files ==="
    # shellcheck disable=SC2016
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci bash -c '
      for file in $(find . -name "*.yml" -o -name "*.yaml"); do
        echo "Checking $file..."
        yamllint "$file" || true
        python3 -c "import yaml; yaml.safe_load(open(\"$file\")); print(\"✅ Valid YAML: $file\")" || echo "❌ Invalid YAML: $file"
      done
    '
    ;;

  json-lint)
    echo "=== Validating JSON files ==="
    # shellcheck disable=SC2016
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci bash -c '
      for file in $(find . -name "*.json"); do
        echo "Checking $file..."
        python3 -m json.tool "$file" > /dev/null && echo "✅ Valid JSON: $file" || echo "❌ Invalid JSON: $file"
      done
    '
    ;;

  autoformat)
    echo "=== Running autoformatters ==="
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci black .
    docker-compose -f "$COMPOSE_FILE" run --rm python-ci isort .
    ;;

  test-gaea2)
    echo "=== Running Gaea2 tests ==="
    # Check if Gaea2 server is available
    GAEA2_URL="${GAEA2_MCP_URL:-http://192.168.0.152:8007}"
    if curl -f -s --connect-timeout 5 --max-time 10 "${GAEA2_URL}/health" > /dev/null 2>&1; then
      echo "✅ Gaea2 MCP server is available at $GAEA2_URL"
      docker-compose run --rm \
        -e PYTHONDONTWRITEBYTECODE=1 \
        -e PYTHONPYCACHEPREFIX=/tmp/pycache \
        -e GAEA2_MCP_URL="${GAEA2_URL}" \
        python-ci bash -c "pip install -r config/python/requirements.txt && pytest tests/gaea2/ -v --tb=short ${EXTRA_ARGS[*]}"
    else
      echo "❌ Gaea2 MCP server is not reachable at $GAEA2_URL"
      echo "⚠️  Skipping Gaea2 tests. To run them, ensure the server is available."
      exit 0
    fi
    ;;

  test-all)
    echo "=== Running all tests (including Gaea2 if server available) ==="
    docker-compose run --rm \
      -e PYTHONDONTWRITEBYTECODE=1 \
      -e PYTHONPYCACHEPREFIX=/tmp/pycache \
      python-ci bash -c "pip install -r config/python/requirements.txt && pytest tests/ -v --cov=. --cov-report=xml --cov-report=term ${EXTRA_ARGS[*]}"
    ;;

  full)
    echo "=== Running full CI checks ==="
    $0 format
    $0 lint-basic
    $0 lint-full
    $0 test
    ;;

  *)
    echo "Unknown stage: $STAGE"
    echo "Available stages: format, lint-basic, lint-full, security, test, test-gaea2, test-all, yaml-lint, json-lint, autoformat, full"
    exit 1
    ;;
esac
