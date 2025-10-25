# GitHub AI Agents - Package Refinement Plan

**Status**: In Progress (Phase 1 Complete)
**Version**: 1.1
**Last Updated**: 2025-10-25
**Purpose**: Bring `github_ai_agents` to the quality standards of `sleeper_detection` and `economic_agents`

## Progress Summary

**Tier 1 Phase 1 Documentation & Testing**: ✅ **Complete**
- ✅ Documentation structure (INDEX.md, QUICK_START.md, INSTALLATION.md)
- ✅ Test reorganization (unit/, integration/, e2e/, tts/)
- ✅ Shared fixtures (conftest.py)
- ✅ Testing guide (tests/README.md)

**Next Up**: Examples overhaul (Phase 3) and board integration implementation

---

## Executive Summary

This document outlines improvements to bring the `github_ai_agents` package up to the quality and maturity standards demonstrated by the other packages in this repository. Based on a comprehensive analysis comparing all three packages (`sleeper_detection`, `economic_agents`, `github_ai_agents`), this plan addresses gaps in documentation, testing structure, examples, tooling, and developer experience.

**Current Status**: Functional but lacks polish
**Target Status**: Production-ready with comprehensive documentation and developer experience

---

## Quality Gap Analysis

### Overall Maturity Comparison

| Aspect | sleeper_detection | economic_agents | github_ai_agents | Gap Level |
|--------|------------------|-----------------|-----------------|-----------|
| **Documentation** | ⭐⭐⭐⭐⭐ (20+ docs) | ⭐⭐⭐⭐ (6 docs) | ⭐⭐ (5 docs) | **HIGH** |
| **Testing Structure** | ⭐⭐⭐⭐⭐ (organized) | ⭐⭐⭐⭐⭐ (parametrized) | ⭐⭐⭐ (flat) | **MEDIUM** |
| **Examples Quality** | ⭐⭐⭐ (1 example) | ⭐⭐⭐⭐⭐ (6 examples + README) | ⭐ (test scripts) | **HIGH** |
| **Project Config** | ⭐⭐⭐⭐⭐ (160 lines) | ⭐⭐⭐⭐ (63 lines) | ⭐⭐⭐ (138 lines) | **MEDIUM** |
| **Tooling/Scripts** | ⭐⭐⭐⭐⭐ (bin/ + scripts/) | ⭐⭐⭐⭐ (examples) | ⭐⭐⭐ (templates) | **MEDIUM** |
| **Version Mgmt** | ⭐⭐⭐⭐ (TODO.md) | ⭐⭐⭐ (versioned) | ⭐ (no changelog) | **HIGH** |

---

## Improvement Plan

### Tier 1: Critical Improvements (Do First)

These items have the highest impact on developer experience and should be completed before the v0.2.0 release (with board integration).

#### 1. Documentation Index & Navigation

**Current State**: 5 disconnected documentation files, no navigation structure

**Target State**: Comprehensive documentation hub with clear navigation

**Deliverables**:
```
packages/github_ai_agents/docs/
├── INDEX.md                      # [NEW] Central documentation hub
├── QUICK_START.md                # [NEW] 5-minute getting started guide
├── INSTALLATION.md               # [NEW] Detailed setup instructions
├── API_REFERENCE.md              # [NEW] Python API documentation
├── CLI_REFERENCE.md              # [NEW] Command-line interface reference
├── architecture.md               # [EXISTS] Keep and enhance
├── security.md                   # [EXISTS] Keep
├── autonomous_mode.md            # [EXISTS] Keep
├── subagents.md                  # [EXISTS] Keep
├── subagents/                    # [EXISTS] Keep directory
│   ├── tech-lead.md
│   ├── security-auditor.md
│   └── qa-reviewer.md
├── tts-integration.md            # [EXISTS] Keep
└── board-integration.md          # [NEW from BOARD_INTEGRATION.md PRD]
```

**INDEX.md Structure** (follow `sleeper_detection` pattern):
```markdown
# GitHub AI Agents Documentation

## Getting Started
- [README](../README.md) - Project overview
- [Quick Start Guide](QUICK_START.md) - Get running in 5 minutes
- [Installation Guide](INSTALLATION.md) - Detailed installation
- [CLI Reference](CLI_REFERENCE.md) - Command reference

## Core Concepts
- [Architecture Overview](architecture.md) - System design
- [Security Model](security.md) - Security and authorization
- [Autonomous Mode](autonomous_mode.md) - Autonomous agent operation

## User Guides
### Monitors
- Issue Monitor - Automated issue processing
- PR Monitor - PR review automation

### Agents
- [Subagents](subagents.md) - Specialized agent types
- Available Agents - Claude, OpenCode, Gemini, Crush

## Advanced Topics
- [TTS Integration](tts-integration.md) - Text-to-speech features
- [Board Integration](board-integration.md) - GitHub Projects v2 integration

## API Reference
- [Python API](API_REFERENCE.md) - Complete API documentation
- [CLI Commands](CLI_REFERENCE.md) - Command-line usage

## Development
- [TODO](../TODO.md) - Development roadmap
- [CHANGELOG](../CHANGELOG.md) - Version history
```

**Implementation Notes**:
- Follow the pattern from `sleeper_detection/docs/INDEX.md`
- Categorize docs by: Getting Started, Core Concepts, User Guides, Advanced Topics, API Reference, Development
- Link to all existing docs and placeholders for new ones

#### 2. Quick Start Guide

**Current State**: README has basic usage but no quick 5-minute guide

**Target State**: `QUICK_START.md` that gets developers productive immediately

**Content Outline**:
```markdown
# Quick Start Guide

## Prerequisites
- Python 3.11+
- GitHub CLI (`gh`)
- GitHub token with repo permissions

## 5-Minute Setup

### Step 1: Installation (1 minute)
# Install from repository
pip install -e packages/github_ai_agents

### Step 2: Configure GitHub Access (1 minute)
export GITHUB_TOKEN=your_github_token
export GITHUB_REPOSITORY=owner/repo

### Step 3: Run Issue Monitor (1 minute)
issue-monitor

### Step 4: Test with Sample Issue (2 minutes)
# Create test issue
gh issue create --title "Test Feature" --body "Implement hello world function [Approved][OpenCode]"

# Monitor processes it automatically
# Check PR created by agent

## Next Steps
- Read [Installation Guide](INSTALLATION.md) for detailed setup
- Learn about [Security Model](security.md)
- Explore [Examples](../examples/)
```

#### 3. Examples Directory Overhaul

**Current State**: `examples/` contains TTS test scripts, not usage examples

**Target State**: Comprehensive examples showing real usage patterns (follow `economic_agents` pattern)

**Structure**:
```
packages/github_ai_agents/examples/
├── README.md                          # [NEW] Comprehensive examples guide
├── basic_usage.py                     # [NEW] Simplest possible usage
├── issue_monitor_example.py           # [NEW] Full issue workflow
├── pr_monitor_example.py              # [NEW] PR review workflow
├── board_integration_example.py       # [NEW] Board usage (after Phase 1)
├── multi_agent_example.py             # [NEW] Coordinating multiple agents
├── custom_agent_example.py            # [NEW] Creating custom agents
├── github_actions_example.yml         # [NEW] Workflow template
├── security_example.py                # [NEW] Security configuration
└── tts/                               # [REORGANIZE] Move TTS examples here
    ├── test_broadcast_report.py       # [MOVE from root]
    ├── test_gemini_tts.py             # [MOVE from root]
    ├── test_voice_catalog.py          # [MOVE from root]
    └── tts_pr_review.sh               # [MOVE from root]
```

**examples/README.md Structure** (follow `economic_agents` pattern):
```markdown
# GitHub AI Agents Examples

## Overview
Examples demonstrating different ways to use the AI Agents framework.

## Examples

### 1. Basic Usage (`basic_usage.py`)
**Purpose**: Simplest way to get started
**Usage**: `python examples/basic_usage.py`
**What it shows**:
- Importing core modules
- Initializing monitors
- Running basic workflows
**Best for**: Quick experiments, learning the API

### 2. Issue Monitor (`issue_monitor_example.py`)
**Purpose**: Complete issue monitoring workflow
**Prerequisites**:
- GitHub repository access
- Issue with trigger comment
**Usage**: `python examples/issue_monitor_example.py`
**What it shows**:
- Setting up issue monitor
- Security configuration
- Agent selection
- PR creation

[... continue for all examples ...]

## Quick Start Patterns

### Pattern 1: Manual Monitoring
[code example]

### Pattern 2: Continuous Monitoring
[code example]

### Pattern 3: GitHub Actions Integration
[code example]

## Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| GITHUB_TOKEN | GitHub API token | Required |
| GITHUB_REPOSITORY | Repository name | Required |
[...]

## Next Steps
1. Start with `basic_usage.py`
2. Try `issue_monitor_example.py`
3. Review the main documentation in `../README.md`
```

#### 4. Test Suite Reorganization

**Current State**: Flat test structure, all tests in `/tests` root

**Target State**: Organized test hierarchy with shared fixtures (follow `economic_agents` pattern)

**Structure**:
```
packages/github_ai_agents/tests/
├── conftest.py                        # [NEW] Shared fixtures
├── README.md                          # [NEW] Testing guide
├── unit/                              # [NEW] Fast, isolated unit tests
│   ├── __init__.py
│   ├── test_agents.py                 # [MOVE from root]
│   ├── test_security.py               # [MOVE from root]
│   ├── test_utils.py                  # [NEW]
│   ├── test_config.py                 # [NEW]
│   └── test_code_parser.py            # [NEW]
├── integration/                       # [NEW] Integration tests
│   ├── __init__.py
│   ├── test_issue_monitor.py          # [MOVE from root]
│   ├── test_pr_monitor.py             # [MOVE from root]
│   ├── test_monitors.py               # [MOVE from root]
│   ├── test_subagents.py              # [MOVE from root]
│   └── test_board_integration.py      # [NEW after Phase 1]
├── e2e/                               # [NEW] End-to-end tests
│   ├── __init__.py
│   ├── test_full_workflow.py          # [NEW]
│   └── test_github_actions.py         # [NEW]
├── tts/                               # [NEW] TTS-specific tests
│   ├── __init__.py
│   ├── test_tts_integration.py        # [MOVE from root]
│   ├── test_tts_unit.py               # [MOVE from root]
│   └── test_voice_profiles.py         # [MOVE from root]
└── fixtures/                          # [NEW] Test data
    ├── sample_issues.json
    ├── sample_prs.json
    └── sample_comments.json
```

**conftest.py** (create comprehensive fixtures like `economic_agents`):
```python
"""Pytest fixtures for GitHub AI Agents tests."""

import pytest
from unittest.mock import Mock, AsyncMock

# Agent Fixtures
@pytest.fixture
def mock_claude_agent():
    """Mock Claude agent for testing."""
    agent = Mock()
    agent.is_available.return_value = True
    agent.get_trigger_keyword.return_value = "Claude"
    agent.generate_code = AsyncMock(return_value="Generated code")
    return agent

@pytest.fixture
def mock_opencode_agent():
    """Mock OpenCode agent for testing."""
    agent = Mock()
    agent.is_available.return_value = True
    agent.get_trigger_keyword.return_value = "OpenCode"
    agent.generate_code = AsyncMock(return_value="Generated code")
    return agent

# Security Fixtures
@pytest.fixture
def security_manager():
    """Security manager with test configuration."""
    from github_ai_agents.security.manager import SecurityManager
    return SecurityManager()

# Monitor Fixtures
@pytest.fixture
def issue_monitor():
    """Issue monitor instance."""
    from github_ai_agents.monitors.issue import IssueMonitor
    return IssueMonitor()

# GitHub API Mock Fixtures
@pytest.fixture
def mock_github_issue():
    """Mock GitHub issue data."""
    return {
        "number": 123,
        "title": "Test Issue",
        "body": "Test body [Approved][OpenCode]",
        "author": {"login": "testuser"},
        "comments": [],
        "labels": []
    }

# ... more fixtures following economic_agents pattern
```

**tests/README.md**:
```markdown
# GitHub AI Agents Test Suite

## Structure

The test suite is organized into four categories:

### Unit Tests (`unit/`)
Fast, isolated tests for individual components. No external dependencies.
- Run with: `pytest tests/unit -v`
- Coverage target: >90%

### Integration Tests (`integration/`)
Tests for component interactions. May use mocked GitHub API.
- Run with: `pytest tests/integration -v`
- Coverage target: >80%

### End-to-End Tests (`e2e/`)
Full workflow tests. May require GitHub credentials.
- Run with: `pytest tests/e2e -v`
- Requires: GITHUB_TOKEN environment variable

### TTS Tests (`tts/`)
Text-to-speech integration tests.
- Run with: `pytest tests/tts -v`

## Running Tests

### All Tests
```bash
pytest tests/ -v --cov=github_ai_agents
```

### Specific Categories
```bash
pytest tests/unit -v          # Unit tests only
pytest tests/integration -v   # Integration tests only
pytest tests/e2e -v           # E2E tests only
```

### With Coverage
```bash
pytest tests/ --cov=github_ai_agents --cov-report=html
```

## Fixtures

See `conftest.py` for available fixtures:
- `mock_claude_agent` - Mock Claude agent
- `mock_opencode_agent` - Mock OpenCode agent
- `security_manager` - Security manager instance
- `issue_monitor` - Issue monitor instance
- `mock_github_issue` - Sample issue data

## Writing Tests

Follow these patterns:

### Unit Test Pattern
```python
def test_agent_availability(mock_claude_agent):
    """Test agent availability check."""
    assert mock_claude_agent.is_available() is True
```

### Integration Test Pattern
```python
async def test_issue_processing(issue_monitor, mock_github_issue):
    """Test full issue processing workflow."""
    result = await issue_monitor.process_issue(mock_github_issue)
    assert result.success is True
```

### E2E Test Pattern
```python
@pytest.mark.e2e
async def test_full_workflow(github_token):
    """Test complete issue-to-PR workflow."""
    # Requires actual GitHub credentials
    pass
```
```

#### 5. CHANGELOG.md Creation

**Current State**: No changelog

**Target State**: Comprehensive changelog following Keep a Changelog format

**File**: `packages/github_ai_agents/CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Projects v2 board integration
- Comprehensive documentation structure
- Examples directory with usage patterns
- Organized test suite (unit/integration/e2e)
- CHANGELOG.md and TODO.md
- bin/ directory with executable wrappers

### Changed
- Reorganized tests into unit/integration/e2e structure
- Moved TTS examples to examples/tts/
- Updated Python requirement to 3.11+
- Updated pyproject.toml line length to 127

### Fixed
- Test coverage improvements
- Documentation gaps

## [0.1.0] - 2024-08-30

### Added
- Initial release
- Issue monitoring with multi-agent support
- PR review monitoring
- Security features with user authorization
- Claude, OpenCode, Gemini, Crush agent support
- TTS integration for PR reviews
- Subagent system (tech-lead, security-auditor, qa-reviewer)

### Features
- Automated code modification for issues and PRs
- Keyword trigger system ([Approved][Agent])
- Rate limiting and repository validation
- Container support for some agents

[Unreleased]: https://github.com/AndrewAltimit/template-repo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AndrewAltimit/template-repo/releases/tag/v0.1.0
```

---

### Tier 2: Important Improvements (Do Soon)

#### 6. API Reference Documentation

**File**: `packages/github_ai_agents/docs/API_REFERENCE.md`

**Structure**:
```markdown
# API Reference

## Core Modules

### Agents (`github_ai_agents.agents`)

#### BaseAgent
Abstract base class for all agents.

**Methods**:
- `is_available() -> bool` - Check if agent is available
- `generate_code(prompt: str, context: dict) -> str` - Generate code
- `get_trigger_keyword() -> str` - Get trigger keyword
- `get_capabilities() -> List[str]` - List capabilities

**Example**:
```python
from github_ai_agents.agents import ClaudeAgent

agent = ClaudeAgent()
if agent.is_available():
    code = await agent.generate_code(
        prompt="Create a function",
        context={"language": "python"}
    )
```

[... continue for all modules ...]

## Monitors (`github_ai_agents.monitors`)
[...]

## Security (`github_ai_agents.security`)
[...]

## CLI (`github_ai_agents.cli`)
[...]
```

#### 7. CLI Reference Documentation

**File**: `packages/github_ai_agents/docs/CLI_REFERENCE.md`

**Structure**:
```markdown
# CLI Reference

## Commands

### `issue-monitor`

Monitor GitHub issues for trigger comments and create PRs.

**Usage**:
```bash
issue-monitor [OPTIONS]
```

**Options**:
- `--repo TEXT` - Repository (overrides GITHUB_REPOSITORY env var)
- `--interval INTEGER` - Polling interval in seconds (default: 300)
- `--continuous` - Run continuously (default: run once)
- `--review-only` - Review mode only, don't create PRs
- `--target-issue INTEGER` - Process specific issue number

**Examples**:
```bash
# Run once
issue-monitor

# Continuous monitoring
issue-monitor --continuous --interval 600

# Review-only mode
issue-monitor --review-only

# Specific issue
issue-monitor --target-issue 123
```

[... continue for all commands ...]
```

#### 8. Installation Guide

**File**: `packages/github_ai_agents/docs/INSTALLATION.md`

**Content**:
```markdown
# Installation Guide

## Prerequisites

- Python 3.11 or higher
- GitHub CLI (`gh`) installed
- GitHub account with repository access
- Git installed

## Installation Methods

### Method 1: Development Installation (Recommended)

Clone repository and install in editable mode:

```bash
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo/packages/github_ai_agents
pip install -e ".[dev]"
```

### Method 2: Production Installation

Install directly from repository:

```bash
pip install git+https://github.com/AndrewAltimit/template-repo.git#subdirectory=packages/github_ai_agents
```

### Method 3: Docker Installation

Use Docker for containerized agents:

```bash
docker-compose run --rm openrouter-agents github-ai-agents
```

## Configuration

### GitHub Token Setup

1. Create GitHub personal access token:
   - Go to Settings → Developer settings → Personal access tokens
   - Create token with `repo` scope

2. Set environment variable:
   ```bash
   export GITHUB_TOKEN=your_github_token_here
   export GITHUB_REPOSITORY=owner/repo
   ```

### Agent API Keys

#### OpenCode/Crush (OpenRouter)
```bash
export OPENROUTER_API_KEY=your_key_here
```

#### Claude (Anthropic)
```bash
export ANTHROPIC_API_KEY=your_key_here  # Optional, CLI is primary
```

[... continue with all setup steps ...]

## Verification

Test installation:

```bash
# Check CLI installed
issue-monitor --help

# Import in Python
python -c "from github_ai_agents.monitors import IssueMonitor; print('Success')"
```

## Troubleshooting

[Common issues and solutions...]
```

#### 9. TODO.md Development Roadmap

**File**: `packages/github_ai_agents/TODO.md`

```markdown
# GitHub AI Agents - Development Roadmap

## Version 0.2.0 - Board Integration (In Progress)

### Features
- [x] GitHub Projects v2 board integration PRD
- [ ] Board manager core implementation
- [ ] Claim system with mutex locks
- [ ] MCP server for board operations
- [ ] Monitor integration (issue/PR → board)
- [ ] CLI tool for board management

### Documentation
- [x] Board integration PRD
- [ ] Board usage examples
- [ ] Board API reference

### Testing
- [ ] Board manager unit tests
- [ ] Claim mechanism tests
- [ ] Integration tests with GitHub Projects

## Version 0.3.0 - Documentation & Polish (Planned)

### Documentation
- [x] Documentation index (INDEX.md)
- [x] Quick start guide
- [x] Installation guide
- [ ] API reference
- [ ] CLI reference
- [ ] Deployment guide
- [ ] Troubleshooting guide

### Examples
- [ ] Comprehensive examples README
- [ ] Basic usage example
- [ ] Issue monitor example
- [ ] PR monitor example
- [ ] Board integration example

### Testing
- [x] Reorganized test structure
- [x] Shared test fixtures (conftest.py)
- [ ] Improved test coverage (>80%)

## Version 0.4.0 - Advanced Features (Future)

### Features
- [ ] Multi-repository board support
- [ ] Advanced agent coordination
- [ ] Workflow templates
- [ ] Analytics dashboard

### Infrastructure
- [ ] Package-level docker-compose
- [ ] CI/CD improvements
- [ ] Performance optimizations

## Backlog

### Features
- [ ] Codex agent support improvements
- [ ] Enhanced TTS features
- [ ] Slack integration
- [ ] Custom webhook triggers

### Technical Debt
- [ ] Migrate to Python 3.11 type hints
- [ ] Async consistency improvements
- [ ] Add Sphinx documentation
- [ ] Improve error handling

### Documentation
- [ ] Video tutorials
- [ ] Interactive examples
- [ ] Best practices guide
```

#### 10. pyproject.toml Updates

**Current Issues**:
- Line length: 120 (should be 127 for consistency)
- Python version: 3.8+ (should be 3.10+ or 3.11+)
- Missing optional dependency groups
- Missing package data for configs

**Changes**:
```toml
[project]
name = "github-ai-agents"
version = "0.2.0"  # Bump for board integration
requires-python = ">=3.11"  # Match other packages
# ... existing fields ...

[project.optional-dependencies]
# Reorganize into feature groups
board = [
    "gql>=3.4.0",  # GraphQL client for GitHub Projects
    "sgqlc>=16.0",  # Alternative GraphQL client
]

tts = [
    "elevenlabs>=0.2.0",  # Text-to-speech
    "pydub>=0.25.0",  # Audio processing
]

mcp = [
    "fastapi>=0.104.0",  # MCP server
    "uvicorn>=0.24.0",
]

dev = [
    # Testing
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    # Type Checking
    "mypy>=1.5.0",
    # Code Quality
    "black>=23.0.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "pylint>=2.17.0",
    # Documentation
    "sphinx>=7.0.0",
    "sphinx-rtd-theme>=1.3.0",
]

all = [
    # Include all optional dependencies
    "gql>=3.4.0",
    "sgqlc>=16.0",
    "elevenlabs>=0.2.0",
    "pydub>=0.25.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.5.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "pylint>=2.17.0",
    "sphinx>=7.0.0",
    "sphinx-rtd-theme>=1.3.0",
]

[tool.setuptools.package-data]
github_ai_agents = [
    "py.typed",
    "*.yaml",
    "*.yml",
    "configs/*.json",      # [NEW] Include config files
    "configs/*.yaml",      # [NEW]
    "templates/*.sh",      # [NEW] Include templates
]

[tool.black]
line-length = 127  # Match other packages (was 120)
target-version = ['py311']  # Update from py38

[tool.flake8]
max-line-length = 127  # [NEW] Add flake8 config
exclude = [".git", "__pycache__", "build", "dist"]
ignore = ["E203", "W503"]

[tool.mypy]
python_version = "3.11"  # Update from 3.8
# ... rest of mypy config ...
```

#### 11. bin/ Directory with Executable Wrappers

**Current State**: No bin/ directory, only entry points in pyproject.toml

**Target State**: Dedicated bin/ directory like sleeper_detection

**Structure**:
```
packages/github_ai_agents/bin/
├── README.md
├── issue-monitor          # Wrapper for issue monitor
├── pr-monitor             # Wrapper for PR monitor
└── board-cli              # Wrapper for board CLI (after Phase 1)
```

**bin/README.md**:
```markdown
# GitHub AI Agents - Executables

This directory contains executable wrappers for the GitHub AI Agents tools.

## Available Commands

### `issue-monitor`
Monitor GitHub issues and automatically create PRs.

**Usage**: `./issue-monitor [options]`
**See**: `issue-monitor --help`

### `pr-monitor`
Monitor pull requests and implement review feedback.

**Usage**: `./pr-monitor [options]`
**See**: `pr-monitor --help`

### `board-cli`
Manage GitHub Project boards for agent coordination.

**Usage**: `./board-cli [command] [options]`
**See**: `board-cli --help`

## Installation

These scripts are automatically added to PATH when you install the package:

```bash
pip install -e .
```

After installation, run commands without `./` prefix:
```bash
issue-monitor
pr-monitor
board-cli
```
```

**bin/issue-monitor** (example):
```bash
#!/usr/bin/env python3
"""Issue monitor executable wrapper."""

import sys
from github_ai_agents.monitors.issue import main

if __name__ == "__main__":
    sys.exit(main())
```

---

### Tier 3: Nice to Have (Future)

#### 12. Deployment Guide

**File**: `packages/github_ai_agents/docs/DEPLOYMENT.md`

Topics to cover:
- Docker deployment
- GitHub Actions setup
- Self-hosted runners
- Environment variables
- Production best practices
- Monitoring and logging

#### 13. Troubleshooting Guide

**File**: `packages/github_ai_agents/docs/TROUBLESHOOTING.md`

Topics to cover:
- Common errors and solutions
- GitHub API issues
- Agent availability problems
- Permission errors
- Rate limiting
- Debug logging

#### 14. Integration Guide

**File**: `packages/github_ai_agents/docs/INTEGRATION_GUIDE.md`

Topics to cover:
- Integrating with existing workflows
- Custom agent development
- Webhook integration
- CI/CD integration
- Custom monitors

#### 15. scripts/ Directory Structure

**Target Structure**:
```
packages/github_ai_agents/scripts/
├── setup/
│   ├── install_hooks.sh
│   └── verify_installation.sh
├── testing/
│   ├── run_unit.sh
│   ├── run_integration.sh
│   ├── run_e2e.sh
│   └── run_all.sh
├── ci/
│   ├── validate.sh
│   ├── lint.sh
│   └── format.sh
└── development/
    ├── generate_docs.sh
    └── update_dependencies.sh
```

#### 16. Package-Level docker-compose.yml

**File**: `packages/github_ai_agents/docker-compose.yml`

Allow standalone package development:
```yaml
version: '3.8'

services:
  github-ai-agents:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_REPOSITORY=${GITHUB_REPOSITORY}
    volumes:
      - ./:/app
    command: pytest tests/ -v

  issue-monitor:
    extends: github-ai-agents
    command: issue-monitor --continuous

  pr-monitor:
    extends: github-ai-agents
    command: pr-monitor --continuous
```

#### 17. Parametrized Test Examples

**File**: `packages/github_ai_agents/tests/README_PARAMETRIZED_TESTS.md`

Follow the `economic_agents` pattern for backend-agnostic testing.

#### 18. Sphinx Documentation

**Setup**:
```
packages/github_ai_agents/docs/
├── conf.py          # Sphinx configuration
├── index.rst        # Sphinx index
├── api/             # Auto-generated API docs
└── _static/         # Static assets
```

#### 19. Test Fixtures Directory

**Structure**:
```
packages/github_ai_agents/tests/fixtures/
├── sample_issues.json       # Sample issue data
├── sample_prs.json          # Sample PR data
├── sample_comments.json     # Sample comment data
├── sample_reviews.json      # Sample review data
└── sample_board_items.json  # Sample board items (after Phase 1)
```

---

## Implementation Checklist

### Tier 1: Critical (Target: v0.2.0)

**Phase 1 - Documentation & Testing** ✅ **COMPLETE** (2025-10-25)
- [x] Create `docs/INDEX.md` with comprehensive navigation
- [x] Create `docs/QUICK_START.md` with 5-minute guide
- [x] Reorganize `tests/` into `unit/`, `integration/`, `e2e/` structure
- [x] Create `tests/conftest.py` with shared fixtures
- [x] Create `tests/README.md` explaining test patterns

**Phase 3 - Examples** (Planned for board integration Phase 3)
- [ ] Overhaul `examples/` directory with real usage examples
- [ ] Create comprehensive `examples/README.md`
- [ ] Move TTS examples to `examples/tts/` subdirectory

**Phase 6 - Tooling & Polish** (Planned for board integration Phase 6)
- [ ] Create `CHANGELOG.md` following Keep a Changelog format
- [ ] Create `TODO.md` with development roadmap

### Tier 2: Important (Target: v0.3.0)

**Completed**
- [x] Create `docs/INSTALLATION.md` with detailed setup guide

**Remaining**
- [ ] Create `docs/API_REFERENCE.md` with complete API documentation
- [ ] Create `docs/CLI_REFERENCE.md` with command reference
- [ ] Update `pyproject.toml`:
  - [ ] Change line length to 127
  - [ ] Update Python requirement to 3.11+
  - [ ] Add optional dependency groups (board, tts, mcp, all)
  - [ ] Add package data for configs and templates
  - [ ] Update tool configurations
- [ ] Create `bin/` directory with executable wrappers
- [ ] Create `bin/README.md` documenting executables

### Tier 3: Nice to Have (Target: v0.4.0)

- [ ] Create `docs/DEPLOYMENT.md`
- [ ] Create `docs/TROUBLESHOOTING.md`
- [ ] Create `docs/INTEGRATION_GUIDE.md`
- [ ] Create `scripts/` directory with development scripts
- [ ] Create package-level `docker-compose.yml`
- [ ] Create `tests/README_PARAMETRIZED_TESTS.md`
- [ ] Setup Sphinx documentation generation
- [ ] Create `tests/fixtures/` directory with test data

---

## Success Metrics

### Documentation
- ✅ Documentation index with navigation
- ✅ At least 10 documentation files (currently 5)
- ✅ Quick start guide <5 minutes
- ✅ Comprehensive examples with README

### Testing
- ✅ Organized test structure (unit/integration/e2e)
- ✅ Shared fixtures in conftest.py
- ✅ Test coverage >80%
- ✅ Test documentation

### Developer Experience
- ✅ Clear installation guide
- ✅ Working examples for all features
- ✅ CHANGELOG tracking changes
- ✅ TODO roadmap visibility

### Package Quality
- ✅ Consistent with other packages (line length, Python version)
- ✅ Comprehensive pyproject.toml
- ✅ bin/ directory with executables
- ✅ Version 0.2.0+ with board integration

---

## Integration with Board Integration PRD

This refinement plan is designed to run alongside the Board Integration PRD (`BOARD_INTEGRATION.md`). The two efforts are complementary:

**Refinement Plan** (this document):
- Focus: Package quality, documentation, developer experience
- Timeline: Progressive, can be done incrementally
- Priority: Tier 1 items should complete before or during board integration

**Board Integration PRD**:
- Focus: Feature development (GitHub Projects v2 integration)
- Timeline: Phased implementation (6 phases)
- Priority: Blocking new feature development

**Recommended Approach**:
1. Complete Tier 1 refinements **during** Board Integration Phase 1-2
2. Complete Tier 2 refinements **during** Board Integration Phase 3-5
3. Complete Tier 3 refinements **after** Board Integration completion

This ensures documentation and testing infrastructure is in place as new features are added.

---

## Notes

- This plan focuses on **structural improvements** and **developer experience**
- No major code refactoring required
- Most work is creating new documentation and reorganizing existing files
- Follows patterns already established by `sleeper_detection` and `economic_agents`
- Can be implemented incrementally without breaking existing functionality

---

**Document Version**: 1.0
**Status**: Draft
**Next Steps**: Review → Prioritize Tier 1 → Implement alongside Board Integration
