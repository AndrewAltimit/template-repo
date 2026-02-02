# Root Tests Directory

This directory contains **integration tests for AI agents and major system workflows**. These tests validate cross-cutting concerns that span multiple packages and services.

## What's in This Directory

| File | Purpose |
|------|---------|
| `test_basic.py` | Basic imports and async functionality smoke tests |
| `test_ai_agent_mcp_tools.py` | AI agent MCP tools integration |
| `test_elevenlabs_streaming.py` | ElevenLabs TTS streaming integration |
| `test_codex_pr_review.py` | Codex PR review workflow automation |
| `test_virtual_character.py` | Virtual character system integration |
| `conftest.py` | Pytest configuration with asyncio plugin |

## Running These Tests

```bash
# Run all root tests (containerized)
docker compose run --rm python-ci pytest tests/ -v

# Run a specific test file
docker compose run --rm python-ci pytest tests/test_codex_pr_review.py -v

# Run with coverage
docker compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml

# Quick test via helper script
./automation/ci-cd/run-ci.sh test
```

## Where Other Tests Live

Tests are distributed throughout the repository, colocated with the code they test:

### Packages

| Package | Location | Description |
|---------|----------|-------------|
| GitHub Agents | `packages/github_agents/tests/` | Unit, integration, and E2E tests for issue/PR monitoring agents |
| Sleeper Agents | `packages/sleeper_agents/tests/` | AI safety detection and trigger sensitivity tests |
| Economic Agents | `packages/economic_agents/tests/` | Economic simulation with unit/integration/validation tests |

### MCP Servers

Each MCP server has its own tests directory under `tools/mcp/`:

| Server | Location |
|--------|----------|
| Gaea2 (Terrain) | `tools/mcp/mcp_gaea2/tests/` |
| Blender (3D) | `tools/mcp/mcp_blender/tests/` |
| Virtual Character | `tools/mcp/mcp_virtual_character/tests/` |
| ElevenLabs Speech | `tools/mcp/mcp_elevenlabs_speech/tests/` |
| Core Library (Rust) | `tools/mcp/mcp_core_rust/` (uses `cargo test`) |
| AgentCore Memory | `tools/mcp/mcp_agentcore_memory/tests/` |
| Code Quality | `tools/mcp/mcp_code_quality/tests/` |
| GitHub Board | `tools/mcp/mcp_github_board/tests/` |

### Automation

| Component | Location |
|-----------|----------|
| Corporate Proxy | `automation/corporate-proxy/tests/` |

## Test Organization Pattern

This repository follows a hierarchical test structure:

```
tests/                    # Root: Cross-package integration tests
packages/<pkg>/tests/
├── unit/                 # Fast, isolated tests (<1s each)
├── integration/          # Component interaction tests
├── e2e/                  # Full workflow tests
└── conftest.py           # Package-specific fixtures
tools/mcp/<server>/tests/ # Server-specific tests
```

## When to Add Tests Here vs. Elsewhere

**Add tests to this directory** when:
- Testing interactions between multiple packages/services
- Validating end-to-end AI agent workflows
- Testing system-wide integration (e.g., PR review pipelines)

**Add tests to package/tool directories** when:
- Testing functionality specific to one package or MCP server
- Writing unit tests for isolated components
- Testing internal APIs that don't cross package boundaries

## Configuration

Test configuration is defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
addopts = "-ra -q --strict-markers"
```

Individual package `conftest.py` files extend this with package-specific fixtures.
