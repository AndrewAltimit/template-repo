# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Support for `GITHUB_PROJECTS_TOKEN` environment variable for board operations
- Enhanced security with separate tokens for Projects v2 (classic) vs repository operations (fine-grained)
- Optional agent pattern in trigger comments (`[Approved]` without specifying agent)
- Agent resolution from board's Agent field when not specified in trigger
- Comprehensive robustness test suites:
  - `test_parser_fuzz.py` - 57 fuzz tests for code parser handling malformed AI responses
  - `test_concurrency.py` - 18 tests for board claim race conditions
  - `test_failure_recovery.py` - 31 tests for claim expiration and error recovery
- `test_optional_agent_resolution.py` - 24 tests for optional agent pattern

### Changed
- BoardManager now prefers `GITHUB_PROJECTS_TOKEN` over `GITHUB_TOKEN` for board operations
- Board CLI updated to check for `GITHUB_PROJECTS_TOKEN` first
- Documentation updated to explain dual token setup and classic token requirement
- Test fixtures updated to support both token types
- SecurityManager now supports `[Approved]` without agent specification
- IssueMonitor and PRMonitor resolve agent from board when not in trigger
- tests/README.md updated with complete unit test listing
- **Trigger consolidation**: `[Fix]` and `[Implement]` merged into `[Approved]`
- Valid triggers now: `[Approved]`, `[Review]`, `[Close]`, `[Summarize]`, `[Debug]`

## [0.2.0] - 2025-10-25

### Added

**GitHub Projects v2 Board Integration**
- GraphQL client for GitHub Projects v2 API
- BoardManager with 15+ async methods
- BoardConfig with YAML configuration
- Issue, AgentClaim, DependencyGraph data models
- Dependency tracking (blockers, parent-child relationships)
- Ready work algorithm (unblocked, unclaimed issues)
- 11 MCP tools for board management:
  - query_ready_work - Get unblocked issues
  - claim_work - Claim issue for implementation
  - renew_claim - Extend claim for long tasks
  - release_work - Release claim (completed/blocked/abandoned/error)
  - update_status - Change issue status
  - add_blocker - Add blocking dependency
  - mark_discovered_from - Mark parent-child relationship
  - get_issue_details - Get full issue context
  - get_dependency_graph - Get dependency graph
  - list_agents - Get enabled agents
  - get_board_config - Get current configuration

**Work Claim System**
- Work claim system with 24-hour timeout
- Claim renewal for long-running tasks
- Concurrent claim conflict prevention
- Session-based tracking
- Comprehensive claim tests

**Monitor Integration**
- Integrated monitors with board for automated work tracking
- Automatic claim management during issue processing
- Status updates throughout workflow
- Issue discovery and dependency tracking

**Command-Line Interface**
- Board CLI with 8 commands (ready, create, block, status, graph, claim, release, info)
- 24 comprehensive unit tests for CLI
- bin/ directory with executable wrappers:
  - issue-monitor - Issue monitoring CLI wrapper
  - pr-monitor - PR monitoring CLI wrapper
  - board-cli - Board management CLI wrapper
  - README.md - Executable documentation

**Docker & Testing**
- Docker setup for board MCP server (port 8021)
- docker-compose integration with health checks
- End-to-end tests for board workflow (10 comprehensive tests)
- CI/CD workflow for board integration testing
- GitHub Actions workflow with 6 jobs

**Documentation & Examples**
- Comprehensive board integration documentation (docs/board-integration.md)
- Complete API reference with 15+ methods documented (docs/API_REFERENCE.md)
- Complete CLI reference for all commands (docs/CLI_REFERENCE.md)
- 9 usage examples:
  - basic_usage.py - Simplest usage patterns
  - issue_monitor_example.py - Complete issue workflow
  - pr_monitor_example.py - PR review workflow
  - board_integration_example.py - GitHub Projects v2 integration
  - multi_agent_example.py - Concurrent agent coordination
  - custom_agent_example.py - Specialized agent creation
  - github_actions_example.yml - GitHub Actions workflow template
  - security_example.py - Security features and best practices
  - README.md - Comprehensive examples guide

### Changed
- Reorganized documentation structure with docs/ directory
- Updated pyproject.toml with board-cli entry point
- Enhanced test fixtures and utilities
- Improved error handling throughout board module
- Updated pre-commit config to exclude bin/ from mypy
- Added mypy exclude for bin/ directory in pyproject.toml

### Fixed
- Integration test hanging issues with proper mocking
- Agent test failures (41/41 unit tests passing)
- Security and priority test fixes
- Mock path issues in integration tests
- Import sorting and formatting conflicts
- Type hints and mypy compliance

## [0.1.0] - 2024-08-30

### Added

**Core Features**
- Issue monitoring with multi-agent support (Claude, OpenCode, Gemini, Crush, Codex)
- PR review monitoring with automated fix implementation
- Security features with user authorization and commit validation
- Keyword trigger system (`[Approved][Agent]`, `[Fix][Agent]`)
- TTS integration for PR reviews using ElevenLabs
- Subagent system (tech-lead, security-auditor, qa-reviewer)

**Infrastructure**
- Automated code modification for issues and PRs
- Multi-agent coordination without conflicts
- OpenRouter API integration for agents
- GitHub GraphQL API client
- Configuration via YAML and environment variables

**Documentation**
- README with installation and usage instructions
- Security model documentation
- Architecture documentation
- Example configurations

### Features
- Continuous monitoring mode for issues and PRs
- Review-only mode for testing
- JSON output for automation
- Agent-specific work filtering
- Priority-based task selection
- Concurrent agent execution

## [0.0.1] - 2024-08-01

### Added
- Initial project structure
- Basic issue and PR monitoring
- GitHub API integration
- Configuration management
- Test suite foundation

---

## Version History

- **0.2.0** (2025-10-25): GitHub Projects v2 board integration
- **0.1.0** (2024-08-30): Initial release with multi-agent support
- **0.0.1** (2024-08-01): Project foundation

## Links

- [Repository](https://github.com/AndrewAltimit/template-repo)
- [Issues](https://github.com/AndrewAltimit/template-repo/issues)
- [Documentation](./docs/)
- [Examples](./examples/)

## Migration Guides

### Upgrading from 0.1.0 to 0.2.0

**New Features Available:**
- GitHub Projects v2 board integration for work tracking
- Board CLI commands for manual board management
- MCP server for board operations (port 8021)

**Configuration Changes:**
- Optional `ai-agents-board.yml` for board integration
- New environment variables:
  - `GITHUB_PROJECT_NUMBER` - Project board number (optional)
  - `BOARD_CONFIG_PATH` - Config file path (optional)

**Breaking Changes:**
- None - all changes are additive and backward compatible

**New Dependencies (Optional):**
```bash
pip install -e .[board]  # For board features
```

**Getting Started with Board Integration:**
1. Create GitHub Project v2 board
2. Configure custom fields (Status, Priority, Agent, etc.)
3. Create `ai-agents-board.yml` configuration
4. Set `GITHUB_PROJECT_NUMBER` environment variable
5. Use `board-cli` commands or MCP tools

See [Board Integration Guide](./docs/board-integration.md) for complete setup instructions.

## Development

### Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Run linting: `pre-commit run --all-files`
6. Submit a pull request

### Release Process

1. Update version in `pyproject.toml`
2. Update this CHANGELOG with new version section
3. Commit changes: `git commit -m "chore: bump version to X.Y.Z"`
4. Tag release: `git tag vX.Y.Z`
5. Push changes: `git push && git push --tags`

## Support

For questions, issues, or feature requests:
- Open an issue: https://github.com/AndrewAltimit/template-repo/issues
- Review documentation: `./docs/`
- Check examples: `./examples/`
