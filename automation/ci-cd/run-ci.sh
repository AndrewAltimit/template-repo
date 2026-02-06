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

# ============================================
# Rust CI Helper Functions
# ============================================

# Track whether Docker images have been built this invocation
_RUST_CI_BUILT=0
_RUST_CI_NIGHTLY_BUILT=0

# Build the Rust CI Docker image (idempotent per invocation)
build_rust_ci() {
  if [ "$_RUST_CI_BUILT" -eq 0 ]; then
    echo "Building Rust CI image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci
    _RUST_CI_BUILT=1
  fi
}

# Build the Rust CI nightly Docker image (idempotent per invocation)
build_rust_ci_nightly() {
  if [ "$_RUST_CI_NIGHTLY_BUILT" -eq 0 ]; then
    echo "Building Rust CI nightly image..."
    docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci-nightly
    _RUST_CI_NIGHTLY_BUILT=1
  fi
}

# Run a cargo command inside the Rust CI container
# Usage: run_cargo <workspace_path> <cargo_args...>
# Pass "." for workspace_path to use the container's default workdir
run_cargo() {
  local workspace_path="$1"
  shift
  build_rust_ci
  if [ "$workspace_path" = "." ]; then
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      rust-ci cargo "$@"
  else
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -w "/app/$workspace_path" \
      rust-ci cargo "$@"
  fi
}

# Standard workspace CI stages
# Usage: run_ws_fmt <workspace_path>
run_ws_fmt()    { run_cargo "$1" fmt --all -- --check; }
run_ws_clippy() { run_cargo "$1" clippy --workspace --all-targets -- -D warnings; }
run_ws_test()   { run_cargo "$1" test --workspace "${EXTRA_ARGS[@]}"; }
run_ws_build()  { run_cargo "$1" build --workspace --all-targets; }
run_ws_deny()   { run_cargo "$1" deny check; }

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
    # Python: Use ruff format (replaces black, 10-100x faster)
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff format .
    # Fix import sorting
    docker compose -f "$COMPOSE_FILE" run --rm python-ci ruff check --select=I --fix .

    # Rust: Format all Rust crates/workspaces
    echo "--- Running Rust autoformat ---"
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env" 2>/dev/null || true

    if command -v cargo &> /dev/null; then
      # Format standalone Rust crates in tools/rust/
      for crate_dir in "$PROJECT_ROOT"/tools/rust/*/; do
        if [ -f "$crate_dir/Cargo.toml" ]; then
          echo "  Formatting $(basename "$crate_dir")..."
          (cd "$crate_dir" && cargo fmt --all 2>&1) || echo "  Warning: cargo fmt failed for $(basename "$crate_dir")"
        fi
      done
      # Format Rust workspace roots
      for workspace_dir in "$PROJECT_ROOT"/packages/*/ "$PROJECT_ROOT"/tools/mcp/mcp_core_rust/; do
        if [ -f "$workspace_dir/Cargo.toml" ]; then
          ws_name="${workspace_dir#"$PROJECT_ROOT"/}"
          echo "  Formatting ${ws_name%/}..."
          (cd "$workspace_dir" && cargo fmt --all 2>&1) || echo "  Warning: cargo fmt failed for ${ws_name%/}"
        fi
      done
    else
      echo "  cargo not available natively, using Docker for Rust formatting..."
      docker compose -f "$COMPOSE_FILE" --profile ci build rust-ci 2>/dev/null || {
        echo "  Warning: Could not build rust-ci image, skipping Rust autoformat"
        true
      }
      # Format tools/rust/* crates via Docker
      for crate_dir in "$PROJECT_ROOT"/tools/rust/*/; do
        if [ -f "$crate_dir/Cargo.toml" ]; then
          crate_name=$(basename "$crate_dir")
          echo "  Formatting $crate_name (Docker)..."
          docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
            -w "/app/tools/rust/$crate_name" \
            rust-ci cargo fmt --all 2>&1 || echo "  Warning: cargo fmt failed for $crate_name"
        fi
      done
      # Format workspace roots via Docker
      for workspace in packages/economic_agents packages/injection_toolkit tools/mcp/mcp_core_rust; do
        if [ -d "$PROJECT_ROOT/$workspace" ]; then
          echo "  Formatting $workspace (Docker)..."
          docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
            -w "/app/$workspace" \
            rust-ci cargo fmt --all 2>&1 || echo "  Warning: cargo fmt failed for $workspace"
        fi
      done
    fi
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
    run_cargo "." fmt --all -- --check
    ;;

  rust-clippy)
    echo "=== Running Rust clippy lints ==="
    # Exclude Windows-only crates that can't compile in the Linux CI container:
    # itk-native-dll: Windows DLL injector (requires Windows SDK)
    # nms-cockpit-injector: Vulkan/OpenVR hooks (uses retour, Windows APIs)
    # nms-video-launcher: Process injection launcher (Windows APIs)
    # nms-video-overlay: Desktop overlay (wgpu/egui/winit with Windows features)
    run_cargo "." clippy --workspace --all-targets \
      --exclude itk-native-dll \
      --exclude nms-cockpit-injector \
      --exclude nms-video-launcher \
      --exclude nms-video-overlay \
      -- -D warnings
    ;;

  rust-test)
    echo "=== Running Rust tests ==="
    # Exclude Windows-only crates (same list as rust-clippy)
    run_cargo "." test --workspace \
      --exclude itk-native-dll \
      --exclude nms-cockpit-injector \
      --exclude nms-video-launcher \
      --exclude nms-video-overlay \
      "${EXTRA_ARGS[@]}"
    ;;

  rust-build)
    echo "=== Building Rust workspace ==="
    # Exclude Windows-only crates (same list as rust-clippy)
    run_cargo "." build --workspace --all-targets \
      --exclude itk-native-dll \
      --exclude nms-cockpit-injector \
      --exclude nms-video-launcher \
      --exclude nms-video-overlay
    ;;

  rust-deny)
    echo "=== Running cargo-deny license/security checks ==="
    run_ws_deny "."
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
    build_rust_ci_nightly
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm \
      -e RUSTFLAGS="--cfg loom" \
      rust-ci-nightly cargo test -p itk-shmem loom_tests -- --nocapture
    ;;

  rust-miri)
    echo "=== Running Miri UB detection ==="
    build_rust_ci_nightly
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci-nightly \
      cargo +nightly miri test -p itk-shmem -- seqlock
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci-nightly \
      cargo +nightly miri test -p itk-protocol
    ;;

  rust-cross-linux)
    echo "=== Cross-compile check (x86_64 Linux) ==="
    build_rust_ci_nightly
    docker compose -f "$COMPOSE_FILE" --profile ci run --rm rust-ci-nightly \
      cargo check --target x86_64-unknown-linux-gnu -p itk-protocol -p itk-shmem -p itk-ipc
    ;;

  rust-cross-windows)
    echo "=== Cross-compile check (Windows) ==="
    build_rust_ci_nightly
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
    run_ws_fmt "packages/economic_agents"
    ;;

  econ-clippy)
    echo "=== Running Economic Agents clippy lints ==="
    run_ws_clippy "packages/economic_agents"
    ;;

  econ-test)
    echo "=== Running Economic Agents tests ==="
    run_ws_test "packages/economic_agents"
    ;;

  econ-build)
    echo "=== Building Economic Agents workspace ==="
    run_ws_build "packages/economic_agents"
    ;;

  econ-deny)
    echo "=== Running Economic Agents cargo-deny checks ==="
    run_ws_deny "packages/economic_agents"
    ;;

  econ-doc)
    echo "=== Generating Economic Agents documentation ==="
    run_cargo "packages/economic_agents" doc --workspace --no-deps --document-private-items
    echo "Documentation generated at packages/economic_agents/target/doc/"
    ;;

  econ-coverage)
    echo "=== Running Economic Agents test coverage ==="
    run_cargo "packages/economic_agents" llvm-cov --workspace --lcov --output-path lcov.info "${EXTRA_ARGS[@]}"
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
    run_ws_fmt "tools/mcp/mcp_core_rust"
    ;;

  mcp-clippy)
    echo "=== Running MCP Core Rust clippy lints ==="
    run_ws_clippy "tools/mcp/mcp_core_rust"
    ;;

  mcp-test)
    echo "=== Running MCP Core Rust tests ==="
    run_ws_test "tools/mcp/mcp_core_rust"
    ;;

  mcp-build)
    echo "=== Building MCP Core Rust workspace ==="
    run_cargo "tools/mcp/mcp_core_rust" build --workspace --all-targets --release
    ;;

  mcp-deny)
    echo "=== Running MCP Core Rust cargo-deny checks ==="
    run_ws_deny "tools/mcp/mcp_core_rust"
    ;;

  mcp-doc)
    echo "=== Generating MCP Core Rust documentation ==="
    run_cargo "tools/mcp/mcp_core_rust" doc --workspace --no-deps --document-private-items
    echo "Documentation generated at tools/mcp/mcp_core_rust/target/doc/"
    ;;

  mcp-full)
    echo "=== Running full MCP Core Rust CI checks ==="
    $0 mcp-fmt
    $0 mcp-clippy
    $0 mcp-test
    ;;

  # ============================================
  # BioForge CI Stages
  # ============================================

  bio-fmt)
    echo "=== Running BioForge format checks ==="
    run_ws_fmt "packages/bioforge"
    echo "=== Running MCP BioForge format checks ==="
    run_cargo "tools/mcp/mcp_bioforge" fmt --all -- --check
    ;;

  bio-clippy)
    echo "=== Running BioForge clippy lints ==="
    run_ws_clippy "packages/bioforge"
    echo "=== Running MCP BioForge clippy lints ==="
    run_cargo "tools/mcp/mcp_bioforge" clippy --all-targets -- -D warnings
    ;;

  bio-test)
    echo "=== Running BioForge tests ==="
    run_ws_test "packages/bioforge"
    ;;

  bio-build)
    echo "=== Building BioForge workspace ==="
    run_ws_build "packages/bioforge"
    echo "=== Building MCP BioForge server ==="
    run_cargo "tools/mcp/mcp_bioforge" build --all-targets
    ;;

  bio-deny)
    echo "=== Running BioForge cargo-deny checks ==="
    run_ws_deny "packages/bioforge"
    ;;

  bio-full)
    echo "=== Running full BioForge CI checks ==="
    $0 bio-fmt
    $0 bio-clippy
    $0 bio-test
    ;;

  # ============================================
  # Tamper Briefcase CI Stages
  # Note: tamper-sensor requires aarch64 (rppal), so clippy/test/build
  # target only the crates that compile on x86_64.
  # ============================================

  tamper-fmt)
    echo "=== Running Tamper Briefcase format checks ==="
    run_ws_fmt "packages/tamper_briefcase"
    ;;

  tamper-clippy)
    echo "=== Running Tamper Briefcase clippy lints ==="
    # tamper-sensor excluded: requires rppal (aarch64 only)
    for crate in tamper-common tamper-gate tamper-challenge tamper-recovery; do
      echo "--- Linting: $crate ---"
      run_cargo "packages/tamper_briefcase" clippy -p "$crate" --all-targets -- -D warnings
    done
    ;;

  tamper-test)
    echo "=== Running Tamper Briefcase tests ==="
    # tamper-sensor excluded: requires rppal (aarch64 only)
    for crate in tamper-common tamper-gate tamper-challenge tamper-recovery; do
      echo "--- Testing: $crate ---"
      run_cargo "packages/tamper_briefcase" test -p "$crate" "${EXTRA_ARGS[@]}"
    done
    ;;

  tamper-build)
    echo "=== Building Tamper Briefcase workspace ==="
    # tamper-sensor excluded: requires rppal (aarch64 only)
    for crate in tamper-common tamper-gate tamper-challenge tamper-recovery; do
      echo "--- Building: $crate ---"
      run_cargo "packages/tamper_briefcase" build -p "$crate" --all-targets
    done
    ;;

  tamper-deny)
    echo "=== Running Tamper Briefcase cargo-deny checks ==="
    run_ws_deny "packages/tamper_briefcase"
    ;;

  tamper-full)
    echo "=== Running full Tamper Briefcase CI checks ==="
    $0 tamper-fmt
    $0 tamper-clippy
    $0 tamper-test
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
    for crate in wrapper-common git-guard gh-validator; do
      echo "--- Checking format: $crate ---"
      run_cargo "tools/rust/$crate" fmt --all -- --check
    done
    ;;

  wrapper-clippy)
    echo "=== Running Wrapper clippy lints ==="
    for crate in wrapper-common git-guard gh-validator; do
      echo "--- Linting: $crate ---"
      run_cargo "tools/rust/$crate" clippy --all-targets -- -D warnings
    done
    ;;

  wrapper-test)
    echo "=== Running Wrapper tests ==="
    for crate in wrapper-common git-guard gh-validator; do
      echo "--- Testing: $crate ---"
      run_cargo "tools/rust/$crate" test
    done
    ;;

  wrapper-full)
    echo "=== Running full Wrapper CI checks ==="
    $0 wrapper-fmt
    $0 wrapper-clippy
    $0 wrapper-test
    ;;

  # ============================================
  # Standalone MCP Server CI Stages
  # Covers all MCP servers outside mcp_core_rust and mcp_bioforge
  # ============================================

  mcp-servers-fmt)
    echo "=== Running standalone MCP server format checks ==="
    FAILED=0
    for server_dir in "$PROJECT_ROOT"/tools/mcp/mcp_*/; do
      server_name=$(basename "$server_dir")
      # Skip mcp_core_rust (has its own stages) and mcp_bioforge (covered by bio-*)
      [ "$server_name" = "mcp_core_rust" ] && continue
      [ "$server_name" = "mcp_bioforge" ] && continue
      [ ! -f "$server_dir/Cargo.toml" ] && continue
      echo "--- Checking format: $server_name ---"
      run_cargo "tools/mcp/$server_name" fmt --all -- --check || FAILED=1
    done
    [ "$FAILED" -eq 0 ] || { echo "FAIL: One or more MCP servers have formatting issues"; exit 1; }
    ;;

  mcp-servers-clippy)
    echo "=== Running standalone MCP server clippy lints ==="
    FAILED=0
    for server_dir in "$PROJECT_ROOT"/tools/mcp/mcp_*/; do
      server_name=$(basename "$server_dir")
      [ "$server_name" = "mcp_core_rust" ] && continue
      [ "$server_name" = "mcp_bioforge" ] && continue
      [ ! -f "$server_dir/Cargo.toml" ] && continue
      echo "--- Linting: $server_name ---"
      run_cargo "tools/mcp/$server_name" clippy --all-targets -- -D warnings || FAILED=1
    done
    [ "$FAILED" -eq 0 ] || { echo "FAIL: One or more MCP servers have clippy warnings"; exit 1; }
    ;;

  mcp-servers-test)
    echo "=== Running standalone MCP server tests ==="
    FAILED=0
    for server_dir in "$PROJECT_ROOT"/tools/mcp/mcp_*/; do
      server_name=$(basename "$server_dir")
      [ "$server_name" = "mcp_core_rust" ] && continue
      [ "$server_name" = "mcp_bioforge" ] && continue
      [ ! -f "$server_dir/Cargo.toml" ] && continue
      echo "--- Testing: $server_name ---"
      run_cargo "tools/mcp/$server_name" test "${EXTRA_ARGS[@]}" || FAILED=1
    done
    [ "$FAILED" -eq 0 ] || { echo "FAIL: One or more MCP server tests failed"; exit 1; }
    ;;

  mcp-servers-full)
    echo "=== Running full standalone MCP server CI checks ==="
    $0 mcp-servers-fmt
    $0 mcp-servers-clippy
    $0 mcp-servers-test
    ;;

  # ============================================
  # Standalone Rust Tools CI Stages
  # Covers tools/rust/* not already in wrapper-* stages
  # ============================================

  tools-fmt)
    echo "=== Running standalone Rust tools format checks ==="
    FAILED=0
    for tool_dir in "$PROJECT_ROOT"/tools/rust/*/; do
      tool_name=$(basename "$tool_dir")
      # Skip wrapper tools (covered by wrapper-* stages)
      [ "$tool_name" = "wrapper-common" ] && continue
      [ "$tool_name" = "git-guard" ] && continue
      [ "$tool_name" = "gh-validator" ] && continue
      [ ! -f "$tool_dir/Cargo.toml" ] && continue
      echo "--- Checking format: $tool_name ---"
      run_cargo "tools/rust/$tool_name" fmt --all -- --check || FAILED=1
    done
    [ "$FAILED" -eq 0 ] || { echo "FAIL: One or more Rust tools have formatting issues"; exit 1; }
    ;;

  tools-clippy)
    echo "=== Running standalone Rust tools clippy lints ==="
    FAILED=0
    for tool_dir in "$PROJECT_ROOT"/tools/rust/*/; do
      tool_name=$(basename "$tool_dir")
      [ "$tool_name" = "wrapper-common" ] && continue
      [ "$tool_name" = "git-guard" ] && continue
      [ "$tool_name" = "gh-validator" ] && continue
      [ ! -f "$tool_dir/Cargo.toml" ] && continue
      echo "--- Linting: $tool_name ---"
      run_cargo "tools/rust/$tool_name" clippy --all-targets -- -D warnings || FAILED=1
    done
    [ "$FAILED" -eq 0 ] || { echo "FAIL: One or more Rust tools have clippy warnings"; exit 1; }
    ;;

  tools-test)
    echo "=== Running standalone Rust tools tests ==="
    FAILED=0
    for tool_dir in "$PROJECT_ROOT"/tools/rust/*/; do
      tool_name=$(basename "$tool_dir")
      [ "$tool_name" = "wrapper-common" ] && continue
      [ "$tool_name" = "git-guard" ] && continue
      [ "$tool_name" = "gh-validator" ] && continue
      [ ! -f "$tool_dir/Cargo.toml" ] && continue
      echo "--- Testing: $tool_name ---"
      run_cargo "tools/rust/$tool_name" test "${EXTRA_ARGS[@]}" || FAILED=1
    done
    [ "$FAILED" -eq 0 ] || { echo "FAIL: One or more Rust tool tests failed"; exit 1; }
    ;;

  tools-full)
    echo "=== Running full standalone Rust tools CI checks ==="
    $0 tools-fmt
    $0 tools-clippy
    $0 tools-test
    ;;

  # ============================================
  # Composite: All Rust CI
  # ============================================

  rust-all)
    echo "=== Running ALL Rust CI checks ==="
    $0 rust-full
    $0 econ-full
    $0 mcp-full
    $0 bio-full
    $0 tamper-full
    $0 wrapper-full
    $0 mcp-servers-full
    $0 tools-full
    ;;

  *)
    echo "Unknown stage: $STAGE"
    echo "Available stages:"
    echo "  Python: format, lint-basic, lint-full, lint-shell, ruff, ruff-fix, bandit, security, test, test-gaea2, test-all, test-corporate-proxy, yaml-lint, json-lint, autoformat, full"
    echo "  Rust (injection_toolkit): rust-fmt, rust-clippy, rust-test, rust-build, rust-deny, rust-full"
    echo "  Rust (nightly):           rust-loom, rust-miri, rust-cross-linux, rust-cross-windows, rust-advanced"
    echo "  Rust (economic_agents):   econ-fmt, econ-clippy, econ-test, econ-build, econ-deny, econ-doc, econ-coverage, econ-full"
    echo "  Rust (mcp_core_rust):     mcp-fmt, mcp-clippy, mcp-test, mcp-build, mcp-deny, mcp-doc, mcp-full"
    echo "  Rust (bioforge+mcp):      bio-fmt, bio-clippy, bio-test, bio-build, bio-deny, bio-full"
    echo "  Rust (tamper_briefcase):  tamper-fmt, tamper-clippy, tamper-test, tamper-build, tamper-deny, tamper-full"
    echo "  Rust (wrapper_guard):     wrapper-fmt, wrapper-clippy, wrapper-test, wrapper-full"
    echo "  Rust (mcp_servers):       mcp-servers-fmt, mcp-servers-clippy, mcp-servers-test, mcp-servers-full"
    echo "  Rust (standalone tools):  tools-fmt, tools-clippy, tools-test, tools-full"
    echo "  Rust (ALL):               rust-all"
    exit 1
    ;;
esac
