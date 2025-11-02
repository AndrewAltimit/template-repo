# AGENTS.md - Universal AI Agent Configuration

This file provides comprehensive guidance for AI agents working with code in this repository.

**For agent-specific expression philosophy and styles, see:**
- Claude: `docs/ai-agents/claude-expression.md`
- Gemini: `docs/ai-agents/gemini-expression.md`

## Project Context

This is a **single-maintainer project** by @AndrewAltimit with a **container-first philosophy**:

- **Zero External Dependencies**: Everything runs in Docker containers
- **Self-hosted Infrastructure**: All CI/CD on self-hosted runners
- **Maximum Portability**: Works on any Linux system with Docker
- **AI-First Development**: Comprehensive multi-agent collaboration system

### Core Architecture Principles

1. **Container-First Development**: All Python operations run in containers
2. **Modular MCP Servers**: Specialized services for specific functionalities
3. **Automated Everything**: From issue creation to PR merging
4. **Security by Design**: Multi-layer validation and authorization

## AI Agent Ecosystem

You are part of a sophisticated multi-agent system:

### Primary Development Agents
- **Claude Code**: Architecture, implementation, debugging (primary development assistant)
- **Gemini CLI**: Automated PR code reviews, container configuration validation
- **OpenCode**: Comprehensive code generation via OpenRouter API
- **Crush**: Fast code generation and quick fixes via OpenRouter API
- **GitHub Copilot**: In-PR code suggestions and improvements

### Automation Agents
- **Issue Monitor Agent**: Automatically creates PRs from GitHub issues
- **PR Review Monitor Agent**: Implements fixes based on review feedback
- **Audit Agent**: Security and compliance monitoring

### Security Model

The agents implement comprehensive security with:
- **Keyword Triggers**: `[Action][Agent]` format (e.g., `[Approved][Claude]`)
- **Allow List**: Only pre-approved users can trigger agents
- **Commit Validation**: Prevents code injection after approval
- **Deterministic Processes**: Predictable, auditable agent behavior

**Full security documentation:** `packages/github_agents/docs/security.md`

## Build/Lint/Test Commands

### Core CI/CD Commands
```bash
# Full CI pipeline - ALWAYS run before committing
./automation/ci-cd/run-ci.sh full

# Individual stages
./automation/ci-cd/run-ci.sh format      # Check formatting
./automation/ci-cd/run-ci.sh lint-basic   # Basic linting
./automation/ci-cd/run-ci.sh lint-full    # Full linting suite
./automation/ci-cd/run-ci.sh autoformat   # Auto-format code
./automation/ci-cd/run-ci.sh test         # Run tests (excludes Gaea2)
./automation/ci-cd/run-ci.sh test-all     # Run all tests including Gaea2
./automation/ci-cd/run-ci.sh security     # Security scanning
```

### Testing Commands
```bash
# Run all tests with coverage (containerized)
docker-compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml

# Run a specific test file
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v

# Run tests with specific test name pattern
docker-compose run --rm python-ci pytest -k "test_format" -v

# Quick test run using helper script (excludes gaea2 tests)
./automation/ci-cd/run-ci.sh test

# Run only Gaea2 tests (requires remote server at 192.168.0.152:8007)
./automation/ci-cd/run-ci.sh test-gaea2
```

### PR Monitoring
```bash
# Monitor a PR for admin/Gemini comments
./automation/monitoring/pr/monitor-pr.sh PR_NUMBER

# Monitor with custom timeout (30 minutes)
./automation/monitoring/pr/monitor-pr.sh PR_NUMBER --timeout 1800

# Monitor from a specific commit (for post-push feedback)
./automation/monitoring/pr/monitor-pr.sh PR_NUMBER --since-commit SHA

# Python agent for monitoring
python automation/monitoring/pr/pr_monitor_agent.py PR_NUMBER
```

## Code Style Guidelines

### Formatting Standards
- **Line Length**: 127 characters (flake8, isort) or 88 (pylint)
- **Python Formatter**: Black with default settings
- **Import Sorting**: isort with Black-compatible profile
- **YAML/JSON**: 2-space indentation

### Naming Conventions
- **Variables/Functions**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Private Members**: _leading_underscore
- **Good Short Names**: i, j, k, e, f, _

### Imports
- **Order**: standard library, third-party, local
- **Style**: Absolute imports preferred
- **Restrictions**: No wildcard imports, no unused imports

### Types
- **Type Hints**: Use where possible, especially for function signatures
- **mypy**: Configured with Python 3.11
- **Configuration**: ignore_missing_imports = True

### Error Handling
- **Specific Exceptions**: Avoid broad exception handling
- **Error Messages**: Include meaningful context
- **Resource Management**: Use context managers
- **Logging**: No f-string interpolation in log messages

### Code Quality Rules
- **No Global Statements**: When possible
- **Class Attributes**: Limit to 15 per class
- **Subprocess Calls**: Use subprocess-run-check
- **Security**: Never hardcode secrets or API keys

## MCP Server Architecture

The project uses modular Model Context Protocol (MCP) servers:

### Core MCP Servers
1. **Code Quality** (Port 8010): Formatting, linting, analysis
2. **Content Creation** (Port 8011): Manim animations, LaTeX compilation
3. **Gemini** (Port 8006): AI integration (host-only, needs Docker access)
4. **Gaea2** (Port 8007): Terrain generation (remote Windows server)
5. **AI Toolkit** (Port 8012): LoRA training (remote GPU machine)
6. **ComfyUI** (Port 8013): Image generation (remote GPU machine)
7. **OpenCode** (Port 8014): AI code generation
8. **Crush** (Port 8015): Fast code generation
9. **Meme Generator** (Local): Meme creation and upload
10. **ElevenLabs Speech** (Port 8018): Advanced TTS with v3 support
11. **Video Editor** (Port 8019): AI-powered video editing
12. **Blender** (Port 8016): 3D content creation
13. **Virtual Character** (Port 8020): AI agent embodiment

### Running MCP Servers
```bash
# Start servers in Docker (recommended)
docker-compose up -d mcp-code-quality
docker-compose up -d mcp-content-creation
docker-compose up -d mcp-gaea2

# Local development (when developing server code)
python -m tools.mcp.code_quality.server
python -m tools.mcp.gemini.server  # Must run on host

# Test all servers
python automation/testing/test_all_servers.py
```

## Container Operations

### Docker Commands
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f mcp-code-quality

# Stop services
docker-compose down

# Rebuild after changes
docker-compose build mcp-code-quality

# Run any command in CI container
docker-compose run --rm python-ci python --version
```

### Container Architecture
- **python-ci**: Main CI/CD container (Python 3.11)
- **MCP Containers**: Individual containers per server
- **OpenRouter Agents**: Containerized AI agents
- **Build Containers**: Specialized for different tasks

## Development Workflow

### Before Starting Work
1. Pull latest changes: `git pull`
2. Check container status: `docker-compose ps`
3. Run tests: `./automation/ci-cd/run-ci.sh test`

### During Development
1. Make changes in appropriate files
2. Run formatting: `./automation/ci-cd/run-ci.sh autoformat`
3. Run linting: `./automation/ci-cd/run-ci.sh lint-basic`
4. Run tests for affected code
5. Check security: `./automation/ci-cd/run-ci.sh security`

### Before Committing
1. **ALWAYS** run full CI: `./automation/ci-cd/run-ci.sh full`
2. Ensure all tests pass
3. Verify no security issues
4. Check that formatting is correct

### PR Workflow
1. Create branch from main
2. Make changes following conventions
3. Push to branch
4. Create PR with descriptive title
5. Monitor for Gemini review feedback
6. Address review comments
7. Wait for approval

## Project Structure

```
template-repo/
├── automation/           # CI/CD and automation scripts
│   ├── ci-cd/           # CI/CD helper scripts
│   ├── monitoring/      # PR and issue monitoring
│   └── security/        # Security validation
├── config/              # Configuration files
│   ├── python/          # Python configs (mypy, pytest)
│   └── docker/          # Docker configurations
├── docker/              # Dockerfiles and requirements
├── docs/                # Documentation
│   ├── ai-agents/       # Agent documentation
│   ├── infrastructure/  # Infrastructure docs
│   └── mcp/             # MCP server docs
├── packages/            # Python packages
│   └── github_agents/ # AI agent implementations
├── tests/               # Test files
├── tools/               # Tool implementations
│   ├── cli/             # CLI tools and scripts
│   └── mcp/             # MCP server implementations
└── outputs/             # Generated outputs
```

## Remote Infrastructure

### Remote Servers
- **Gaea2 Server**: Windows machine at `192.168.0.152:8007`
- **AI Toolkit**: GPU machine at `192.168.0.152:8012`
- **ComfyUI**: GPU machine at `192.168.0.152:8013`

**Important**: Do NOT change remote addresses to localhost in PR reviews

## Security Best Practices

1. **Never commit secrets**: Use environment variables
2. **Validate inputs**: Check all external data
3. **Use allow lists**: For user authorization
4. **Audit logs**: Maintain audit trails
5. **Container isolation**: Keep services separated
6. **Least privilege**: Minimal permissions

## Testing Strategy

### Test Types
- **Unit Tests**: Individual function/class testing
- **Integration Tests**: Service interaction testing
- **E2E Tests**: Full workflow validation
- **Security Tests**: Vulnerability scanning

### Test Requirements
- **Coverage**: Maintain >80% code coverage
- **Mocking**: Mock external dependencies
- **Fixtures**: Use pytest fixtures
- **Async Support**: pytest-asyncio for async code

## Common Patterns

### MCP Server Development
```python
from tools.mcp.core import BaseMCPServer

class MyServer(BaseMCPServer):
    def __init__(self):
        super().__init__("my_server", port=8020)
```

### Error Handling
```python
try:
    result = operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise
finally:
    cleanup()
```

### Testing Pattern
```python
@pytest.fixture
def mock_client():
    with patch('module.client') as mock:
        yield mock

def test_function(mock_client):
    mock_client.return_value = expected
    assert function() == expected
```

## Documentation Standards

### Code Documentation
- **Docstrings**: Google style for all public functions/classes
- **Type Hints**: Required for function signatures
- **Comments**: Explain "why", not "what"
- **README Files**: Each major component needs one

### Commit Messages
- **Format**: `type: description` (e.g., `feat: add new MCP server`)
- **Types**: feat, fix, docs, style, refactor, test, chore
- **Body**: Explain motivation and changes
- **References**: Link to issues/PRs

## Troubleshooting

### Common Issues
1. **Permission Errors**: Run `./automation/setup/runner/fix-runner-permissions.sh`
2. **Container Build Fails**: Check Docker daemon status
3. **Tests Fail Locally**: Ensure containers are running
4. **Import Errors**: Verify Python path and virtual env

### Debug Commands
```bash
# Check container logs
docker-compose logs -f [service_name]

# Shell into container
docker-compose run --rm python-ci bash

# Check Python path
docker-compose run --rm python-ci python -c "import sys; print(sys.path)"

# Verify installations
docker-compose run --rm python-ci pip list
```

## Quick Reference

### Essential Commands
```bash
# Full CI check
./automation/ci-cd/run-ci.sh full

# Auto-format code
./automation/ci-cd/run-ci.sh autoformat

# Run specific test
docker-compose run --rm python-ci pytest tests/test_file.py -v

# Monitor PR
./automation/monitoring/pr/monitor-pr.sh PR_NUMBER

# View logs
docker-compose logs -f service_name
```

### Key Files
- `CLAUDE.md`: Claude-specific instructions
- `GEMINI.md`: Gemini-specific context
- `CRUSH.md`: Crush agent configuration
- `docker-compose.yml`: Service definitions
- `pyproject.toml`: Python tool configurations
- `.github/workflows/`: CI/CD workflows

## Additional Resources

- **Security Documentation**: `packages/github_agents/docs/security.md`
- **MCP Architecture**: `docs/mcp/README.md`
- **AI Agent Matrix**: `docs/ai-agents/agent-matrix.md`
- **Infrastructure Guide**: `docs/infrastructure/README.md`
- **Integration Docs**: `docs/integrations/README.md`

---

**Remember**: This is a container-first, AI-driven project. Always use containers for consistency, follow the security model, and leverage the multi-agent system for maximum efficiency.
