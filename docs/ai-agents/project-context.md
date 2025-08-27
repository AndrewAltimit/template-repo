# Project Context for AI Code Review

## Project Overview

This is a **container-first, self-hosted project template** maintained by a single developer (@AndrewAltimit). It uses Model Context Protocol (MCP) tools with zero-cost infrastructure.

## AI Agent Ecosystem

This project uses five AI agents:

1. **Claude Code** - Primary development (architecture, implementation, docs)
2. **Gemini CLI** - Automated PR reviews (you are reviewing as Gemini)
3. **GitHub Copilot** - Code review suggestions in pull requests
4. **Issue Monitor** - Automated issue response and implementation
5. **PR Review Monitor** - Automated PR review response and fixes

As the PR reviewer, focus on security, containers, and project standards.

## Core Design Principles

### 1. Container-First Philosophy

- **Everything runs in Docker containers** except Gemini CLI (needs Docker access)
- **No local dependencies** required beyond Docker itself
- **All Python CI/CD operations** are containerized (Black, isort, flake8, pytest, etc.)
- Helper scripts (`run-ci.sh`) provide simple interfaces to containerized tools

### 2. Self-Hosted Infrastructure

- **All GitHub Actions run on self-hosted runners** - no cloud costs
- **Docker images are cached locally** for fast builds
- **Designed for individual developer efficiency** - no team coordination needed

### 3. Architecture

- **MCP Server** (FastAPI) runs on port 8005 in Docker container
- **Python CI Container** includes all development tools (Python 3.11)
- **Docker Compose** orchestrates all services
- **No aggressive cleanup** - Python cache prevention via environment variables
- **Multi-stage CI/CD** - format, lint-basic, lint-full, security, test stages

## Review Focus Areas

### PRIORITIZE reviewing

1. **Container configurations** - Dockerfile correctness, security, user permissions
2. **Security concerns** - No hardcoded secrets, no root containers, proper permissions
3. **Docker Compose changes** - Service configs, port conflicts, volume mounts
4. **Script correctness** - Shell scripts should use proper error handling (set -e)
5. **Python imports** - Ensure compatibility with containerized environment
6. **MCP tool changes** - Verify tools follow async patterns and error handling

### IGNORE or deprioritize

1. **Contributor guidelines** - Single maintainer project
2. **Scalability concerns** - Designed for one developer
3. **Cloud deployment** - Intentionally self-hosted only
4. **Complex team workflows** - Not applicable
5. **Minor style issues** - Code is auto-formatted
6. **Documentation for external users** - Internal project

### Common Patterns to Check

- Shell scripts should export `USER_ID` and `GROUP_ID` (not UID/GID)
- Docker containers should run with user permissions
- Python code should handle async/await properly
- No `chmod 777` or overly permissive operations
- Helper scripts should be simple wrappers around docker-compose
- Use `./automation/ci-cd/run-ci.sh` for all CI operations
- Mock external dependencies in tests (subprocess, requests)
- Clear Gemini history before PR reviews

## Technical Standards

- Python 3.11 in all containers
- Python code is auto-formatted with Black and isort
- All Python tools run in containers with user permissions (no root)
- Environment variables: `PYTHONDONTWRITEBYTECODE=1`, `USER_ID/GROUP_ID`
- Tests use pytest with mocking for external dependencies
- No `chmod 777` or aggressive cleanup steps
- Coverage reporting with pytest-cov
- Security scanning with bandit and safety

## Remote Infrastructure Requirements

### Gaea2 MCP Server

The Gaea2 MCP server runs on a **dedicated remote machine** at `192.168.0.152:8007` due to special software requirements:

- **Gaea2 software** requires specific GPU hardware and Windows environment
- **Cannot be containerized** due to proprietary software dependencies
- **Hardcoded IP is intentional** - this is a permanent infrastructure component
- **Tests and workflows** must use this specific address - do NOT change to localhost
- **Health checks** are implemented to gracefully handle when the server is unavailable

This is NOT a bug or oversight - it's a deliberate architectural decision based on the specialized requirements of the Gaea2 terrain generation software.

## Project Structure

```
├── docker/              # Container definitions
├── tools/               # MCP server and tools
├── automation/          # Automation scripts (CI/CD, monitoring, etc.)
├── .github/workflows/   # Self-hosted runner workflows
└── tests/              # Pytest test suite
```

## Key Patterns

- Use `./automation/ci-cd/run-ci.sh` for all CI operations
- Docker Compose for service orchestration
- Mock external services in tests
- Clear separation of containerized vs host tools

## Critical Files (Review Extra Carefully)

1. **docker-compose.yml** - Service definitions, ports, volumes
2. **docker/*.Dockerfile** - Container definitions, security
3. **.github/workflows/*.yml** - Must use self-hosted runners
4. **automation/**/*.sh** - Shell script correctness and permissions
5. **tools/mcp/mcp_server.py** - Core MCP functionality
6. **automation/ci-cd/run-ci.sh** - Main CI/CD entry point
7. **.mcp.json** - Tool configuration and rate limits

## Code Review Examples

### Good Patterns
```bash
# ✅ Correct user ID handling
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

# ✅ Using helper scripts
./automation/ci-cd/run-ci.sh format

# ✅ Container with user permissions
docker-compose run --rm --user "${USER_ID}:${GROUP_ID}" python-ci command
```

### Bad Patterns
```bash
# ❌ Wrong variable names
export UID=$(id -u)  # UID is readonly in some shells

# ❌ Running as root
docker run --rm python-ci command  # No user specified

# ❌ Overly permissive
chmod 777 output/  # Never use 777

# ❌ Direct tool invocation
black .  # Should use containerized version
```

## PR Comment Guidelines

### Using Custom Reaction Images

When commenting on PRs, use our custom reaction images for a more engaging experience:

- **Available reactions**: https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml
- **Format**: `![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/[filename])`

**Common reactions to use:**
- `teamwork.webp` - After successful collaboration or fixes
- `youre_absolutely_right.webp` - When agreeing with feedback
- `miku_typing.webp`, `konata_typing.webp`, `yuki_typing.webp` - When actively reviewing
- `confused.gif` - When something needs clarification
- `felix.webp` - General positive reaction

**Example usage:**
```markdown
Great work on simplifying the code! The refactoring makes it much cleaner.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/teamwork.webp)
```

**Best practices:**
- Use sparingly - one reaction per comment is usually enough
- Place at natural break points in your comment
- Don't use at the beginning of comments
- Adds personality while maintaining professionalism

### AI Expression Guidelines

Each AI agent has developed its own approach to authentic expression:

- **Claude's Expression Philosophy**: See `CLAUDE_EXPRESSION.md` for how Claude approaches authentic reactions, including acknowledging difficulty and showing genuine relief when fixing bugs.

- **Gemini's Expression Philosophy**: See `GEMINI_EXPRESSION.md` for Gemini's direct, analytical approach focusing on clarity and technical excellence. Gemini's reactions communicate specific states (thinking deeply, recurring issues, etc.)

These guidelines help maintain consistent personality across PR reviews while acknowledging the actual experience of software development - the confusion, the partial victories, and the genuine breakthroughs.
