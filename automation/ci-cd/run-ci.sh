#!/bin/bash
# CI/CD Helper Script for running Python and Rust tools in Docker
# This simplifies repetitive docker compose commands in workflows
#
# Python CI: Uses python-ci container (Python 3.11)
# Rust CI:   Uses rust-ci container (Rust 1.83) for injection_toolkit

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

# Export user IDs for docker compose
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# Export Python cache prevention variables
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX=/tmp/pycache

# Set ruff output format based on environment (github annotations in CI, concise locally)
if [ -n "$CI" ]; then
  RUFF_OUTPUT_FORMAT="github"
else
  RUFF_OUTPUT_FORMAT="concise"
fi

# Ensure cache directories exist (prevents Docker from creating them as root)
mkdir -p ~/.cache/uv ~/.cache/pre-commit

# Build the CI image if needed
echo "🔨 Building CI image..."
docker compose -f "$COMPOSE_FILE" build python-ci

case "$STAGE" in
  format)
    echo "=== Running format checks ==="
    # Use ruff format (replaces black, 10-100x faster)
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff format --check --diff .
    # Check import sorting
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --select=I --diff .
    ;;

  lint-basic)
    echo "=== Running basic linting ==="
    # Format check (ruff format replaces black)
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff format --check .
    # Import sorting check
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --select=I .
    # Critical errors (ruff replaces flake8 for E9,F63,F7,F82)
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --select=E9,F63,F7,F82 --output-format="$RUFF_OUTPUT_FORMAT" .
    # Style check (informational)
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --select=E,W,C90 --exit-zero --output-format=grouped .
    ;;

  lint-full)
    echo "=== Running full linting suite ==="
    # Format check (ruff format replaces black)
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff format --check .
    # Import sorting check
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --select=I .
    # Full ruff check (replaces flake8 and pylint) - informational, doesn't fail
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --exit-zero --output-format="$RUFF_OUTPUT_FORMAT" .
    # Type checking with ty (Astral's fast type checker, replaces mypy)
    # ty is 10-60x faster than mypy with millisecond incremental updates
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ty check . || true
    ;;

  ruff)
    echo "=== Running Ruff (fast linter) ==="
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check . --output-format=github
    ;;

  ruff-fix)
    echo "=== Running Ruff with auto-fix ==="
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check . --fix
    ;;

  bandit)
    echo "=== Running Bandit security scan ==="
    docker compose -f "$COMPOSE_FILE" run --rm python-ci bandit -r . -c pyproject.toml -f txt
    ;;

  security)
    echo "=== Running security scans ==="
    docker compose -f "$COMPOSE_FILE" run --rm python-ci bandit -r . -f json -o bandit-report.json || true
    # Dependency security check - try Safety with API key, fallback to pip-audit
    if [ -n "$SAFETY_API_KEY" ]; then
      echo "Using Safety with API key..."
      docker compose -f "$COMPOSE_FILE" run --rm -T -e SAFETY_API_KEY="$SAFETY_API_KEY" python-ci safety scan --key "$SAFETY_API_KEY" --disable-optional-telemetry --output json > safety-report.json || true
    else
      echo "No SAFETY_API_KEY found, using pip-audit instead..."
      docker compose -f "$COMPOSE_FILE" run --rm -T python-ci python -m pip_audit --format json > safety-report.json || true
    fi
    ;;

  test)
    echo "=== Running tests ==="
    # Include corporate-proxy tests in the main test suite
    # Using pytest-xdist for parallel test execution (packages already installed in image)
    # Note: MCP server tests are now in Rust (run via 'cargo test' in each mcp_* directory)
    docker compose run --rm \
      -e PYTHONDONTWRITEBYTECODE=1 \
      -e PYTHONPYCACHEPREFIX=/tmp/pycache \
      python-ci pytest tests/ automation/corporate-proxy/tests/ -v -n auto --cov=. --cov-report=xml --cov-report=html --cov-report=term "${EXTRA_ARGS[@]}"

    # Run additional corporate proxy component tests (scripts, not pytest)
    echo "=== Testing corporate proxy components ==="
    docker compose run --rm python-ci python automation/corporate-proxy/shared/scripts/test-auto-detection.py
    docker compose run --rm python-ci python automation/corporate-proxy/shared/scripts/test-content-stripping.py
    ;;

  yaml-lint)
    echo "=== Validating YAML files ==="
    # shellcheck disable=SC2016
    docker compose -f "$COMPOSE_FILE" run --rm python-ci bash -c '
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
    docker compose -f "$COMPOSE_FILE" run --rm python-ci bash -c '
      for file in $(find . -name "*.json"); do
        echo "Checking $file..."
        python3 -m json.tool "$file" > /dev/null && echo "✅ Valid JSON: $file" || echo "❌ Invalid JSON: $file"
      done
    '
    ;;

  lint-shell)
    echo "=== Linting shell scripts with shellcheck ==="
    # shellcheck disable=SC2016
    docker compose -f "$COMPOSE_FILE" run --rm python-ci bash -c '
      echo "Running shellcheck on all .sh files..."
      ISSUES_FOUND=0
      for script in $(find . -name "*.sh" -type f); do
        echo "Checking $script..."
        if shellcheck -S warning "$script"; then
          echo "OK $script"
        else
          echo "FAIL $script has issues"
          ISSUES_FOUND=1
        fi
      done

      if [ $ISSUES_FOUND -ne 0 ]; then
        echo ""
        echo "FAIL Shell linting failed: issues were found in your shell scripts."
        echo "Please fix all the reported shellcheck errors to continue."
        exit 1
      else
        echo ""
        echo "OK All shell scripts passed linting!"
      fi
    '
    ;;

  autoformat)
    echo "=== Running autoformatters ==="
    # Use ruff format (replaces black, 10-100x faster)
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff format .
    # Fix import sorting
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --select=I --fix .
    ;;

  test-gaea2)
    echo "=== Running Gaea2 tests ==="
    # Check if Gaea2 server is available
    GAEA2_URL="${GAEA2_MCP_URL:-http://192.168.0.152:8007}"
    if curl -f -s --connect-timeout 5 --max-time 10 "${GAEA2_URL}/health" > /dev/null 2>&1; then
      echo "✅ Gaea2 MCP server is available at $GAEA2_URL"
      docker compose run --rm \
        -e PYTHONDONTWRITEBYTECODE=1 \
        -e PYTHONPYCACHEPREFIX=/tmp/pycache \
        -e GAEA2_MCP_URL="${GAEA2_URL}" \
        python-ci pytest tools/mcp/mcp_gaea2/tests/ -v --tb=short "${EXTRA_ARGS[@]}"
    else
      echo "❌ Gaea2 MCP server is not reachable at $GAEA2_URL"
      echo "⚠️  Skipping Gaea2 tests. To run them, ensure the server is available."
      exit 0
    fi
    ;;

  test-all)
    echo "=== Running all tests (including Gaea2 if server available) ==="
    # Using pytest-xdist for parallel execution (packages already installed in image)
    docker compose run --rm \
      -e PYTHONDONTWRITEBYTECODE=1 \
      -e PYTHONPYCACHEPREFIX=/tmp/pycache \
      python-ci pytest tests/ -v -n auto --cov=. --cov-report=xml --cov-report=term "${EXTRA_ARGS[@]}"
    ;;

  test-corporate-proxy)
    echo "=== Running corporate proxy tests ==="
    docker compose run --rm \
      -e PYTHONDONTWRITEBYTECODE=1 \
      -e PYTHONPYCACHEPREFIX=/tmp/pycache \
      --user "${USER_ID}:${GROUP_ID}" \
      python-ci python -m pytest \
      automation/corporate-proxy/tests/ \
      -v -n auto \
      --tb=short \
      --no-header "${EXTRA_ARGS[@]}"
    ;;

  # ============================================
  # Rust CI Stages (injection_toolkit)
  # ============================================

  rust-fmt)
    echo "=== Running Rust format checks ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci cargo fmt --all -- --check
    ;;

  rust-clippy)
    echo "=== Running Rust clippy lints ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    # Exclude Windows-only crates that can't compile in the Linux CI container:
    # itk-native-dll: Windows DLL injector (requires Windows SDK)
    # nms-cockpit-injector: Vulkan/OpenVR hooks (uses retour, Windows APIs)
    # nms-video-launcher: Process injection launcher (Windows APIs)
    # nms-video-overlay: Desktop overlay (wgpu/egui/winit with Windows features)
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci cargo clippy \
      --workspace --all-targets \
      --exclude itk-native-dll \
      --exclude nms-cockpit-injector \
      --exclude nms-video-launcher \
      --exclude nms-video-overlay \
      -- -D warnings
    ;;

  rust-test)
    echo "=== Running Rust tests ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    # Exclude Windows-only crates (same list as rust-clippy)
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci cargo test \
      --workspace \
      --exclude itk-native-dll \
      --exclude nms-cockpit-injector \
      --exclude nms-video-launcher \
      --exclude nms-video-overlay \
      "${EXTRA_ARGS[@]}"
    ;;

  rust-build)
    echo "=== Building Rust workspace ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    # Exclude Windows-only crates (same list as rust-clippy)
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci cargo build \
      --workspace --all-targets \
      --exclude itk-native-dll \
      --exclude nms-cockpit-injector \
      --exclude nms-video-launcher \
      --exclude nms-video-overlay
    ;;

  rust-deny)
    echo "=== Running cargo-deny license/security checks ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci cargo deny check || true
    ;;

  rust-full)
    echo "=== Running full Rust CI checks ==="
    $0 rust-fmt
    $0 rust-clippy
    $0 rust-test
    ;;

  # ============================================
  # Advanced Rust CI Stages (nightly container)
  # ============================================

  rust-loom)
    echo "=== Running Loom concurrency tests ==="
    echo "Building Rust CI nightly image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci-nightly
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -e RUSTFLAGS="--cfg loom" \
      rust-ci-nightly cargo test -p itk-shmem loom_tests -- --nocapture
    ;;

  rust-miri)
    echo "=== Running Miri UB detection ==="
    echo "Building Rust CI nightly image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci-nightly
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci-nightly \
      cargo +nightly miri test -p itk-shmem -- seqlock
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci-nightly \
      cargo +nightly miri test -p itk-protocol
    ;;

  rust-cross-linux)
    echo "=== Cross-compile check (x86_64 Linux) ==="
    echo "Building Rust CI nightly image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci-nightly
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci-nightly \
      cargo check --target x86_64-unknown-linux-gnu -p itk-protocol -p itk-shmem -p itk-ipc
    ;;

  rust-cross-windows)
    echo "=== Cross-compile check (Windows) ==="
    echo "Building Rust CI nightly image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci-nightly
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci-nightly \
      cargo check --target x86_64-pc-windows-gnu -p itk-protocol -p itk-shmem -p itk-ipc
    ;;

  rust-advanced)
    echo "=== Running advanced Rust CI checks (nightly) ==="
    $0 rust-loom
    $0 rust-miri
    $0 rust-cross-linux
    $0 rust-cross-windows
    ;;

  # ============================================
  # Economic Agents Rust CI Stages
  # ============================================

  econ-fmt)
    echo "=== Running Economic Agents format checks ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/packages/economic_agents \
      rust-ci cargo fmt --all -- --check
    ;;

  econ-clippy)
    echo "=== Running Economic Agents clippy lints ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/packages/economic_agents \
      rust-ci cargo clippy --workspace --all-targets -- -D warnings
    ;;

  econ-test)
    echo "=== Running Economic Agents tests ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/packages/economic_agents \
      rust-ci cargo test --workspace "${EXTRA_ARGS[@]}"
    ;;

  econ-build)
    echo "=== Building Economic Agents workspace ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/packages/economic_agents \
      rust-ci cargo build --workspace --all-targets
    ;;

  econ-deny)
    echo "=== Running Economic Agents cargo-deny checks ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/packages/economic_agents \
      rust-ci cargo deny check || true
    ;;

  econ-doc)
    echo "=== Generating Economic Agents documentation ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/packages/economic_agents \
      rust-ci cargo doc --workspace --no-deps --document-private-items
    echo "Documentation generated at packages/economic_agents/target/doc/"
    ;;

  econ-coverage)
    echo "=== Running Economic Agents test coverage ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/packages/economic_agents \
      rust-ci cargo llvm-cov --workspace --lcov --output-path lcov.info "${EXTRA_ARGS[@]}"
    echo "Coverage report generated at packages/economic_agents/lcov.info"
    ;;

  econ-full)
    echo "=== Running full Economic Agents CI checks ==="
    $0 econ-fmt
    $0 econ-clippy
    $0 econ-test
    ;;

  # ============================================
  # MCP Core Rust CI Stages
  # ============================================

  mcp-fmt)
    echo "=== Running MCP Core Rust format checks ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/tools/mcp/mcp_core_rust \
      rust-ci cargo fmt --all -- --check
    ;;

  mcp-clippy)
    echo "=== Running MCP Core Rust clippy lints ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/tools/mcp/mcp_core_rust \
      rust-ci cargo clippy --workspace --all-targets -- -D warnings
    ;;

  mcp-test)
    echo "=== Running MCP Core Rust tests ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/tools/mcp/mcp_core_rust \
      rust-ci cargo test --workspace "${EXTRA_ARGS[@]}"
    ;;

  mcp-build)
    echo "=== Building MCP Core Rust workspace ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/tools/mcp/mcp_core_rust \
      rust-ci cargo build --workspace --all-targets --release
    ;;

  mcp-deny)
    echo "=== Running MCP Core Rust cargo-deny checks ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/tools/mcp/mcp_core_rust \
      rust-ci cargo deny check || true
    ;;

  mcp-doc)
    echo "=== Generating MCP Core Rust documentation ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w /app/tools/mcp/mcp_core_rust \
      rust-ci cargo doc --workspace --no-deps --document-private-items
    echo "Documentation generated at tools/mcp/mcp_core_rust/target/doc/"
    ;;

  mcp-full)
    echo "=== Running full MCP Core Rust CI checks ==="
    $0 mcp-fmt
    $0 mcp-clippy
    $0 mcp-test
    ;;

  full)
    echo "=== Running full CI checks ==="
    $0 format
    $0 lint-basic
    $0 lint-full
    $0 lint-shell
    $0 test
    $0 test-corporate-proxy
    ;;

  # ============================================
  # Wrapper Guard CI Stages (wrapper-common, git-guard, gh-validator)
  # ============================================

  wrapper-fmt)
    echo "=== Running Wrapper format checks ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    for crate in wrapper-common git-guard gh-validator; do
      echo "--- Checking format: $crate ---"
      docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
        -w /app/tools/rust/$crate \
        rust-ci cargo fmt --all -- --check
    done
    ;;

  wrapper-clippy)
    echo "=== Running Wrapper clippy lints ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    for crate in wrapper-common git-guard gh-validator; do
      echo "--- Linting: $crate ---"
      docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
        -w /app/tools/rust/$crate \
        rust-ci cargo clippy --all-targets -- -D warnings
    done
    ;;

  wrapper-test)
    echo "=== Running Wrapper tests ==="
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    for crate in wrapper-common git-guard gh-validator; do
      echo "--- Testing: $crate ---"
      docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
        -w /app/tools/rust/$crate \
        rust-ci cargo test
    done
    ;;

  wrapper-full)
    echo "=== Running full Wrapper CI checks ==="
    $0 wrapper-fmt
    $0 wrapper-clippy
    $0 wrapper-test
    ;;

  *)
    echo "Unknown stage: $STAGE"
    echo "Available stages:"
    echo "  Python: format, lint-basic, lint-full, lint-shell, ruff, ruff-fix, bandit, security, test, test-gaea2, test-all, test-corporate-proxy, yaml-lint, json-lint, autoformat, full"
    echo "  Rust (injection_toolkit): rust-fmt, rust-clippy, rust-test, rust-build, rust-deny, rust-full"
    echo "  Rust (nightly):           rust-loom, rust-miri, rust-cross-linux, rust-cross-windows, rust-advanced"
    echo "  Rust (economic_agents):   econ-fmt, econ-clippy, econ-test, econ-build, econ-deny, econ-doc, econ-coverage, econ-full"
    echo "  Rust (mcp_core_rust):     mcp-fmt, mcp-clippy, mcp-test, mcp-build, mcp-deny, mcp-doc, mcp-full"
    echo "  Rust (wrapper_guard):     wrapper-fmt, wrapper-clippy, wrapper-test, wrapper-full"
    exit 1
    ;;
esac
