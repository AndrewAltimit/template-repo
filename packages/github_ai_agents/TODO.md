# GitHub AI Agents - Development Roadmap

## Version 0.2.0 - Board Integration (In Progress)

**Branch:** `github-agents-refine`
**Current Phase:** Phase 5 (Phases 1-4 Complete)
**Last Updated:** 2025-10-25

---

### Phase 1: Foundation & GraphQL Client ✅ COMPLETE

**Status:** All deliverables completed and tested

**Accomplishments:**
- [x] Core module structure (board/__init__.py, errors.py, models.py, config.py)
- [x] BoardManager with GraphQL client (1,076 lines)
  - Complete GraphQL operations (queries, mutations)
  - Project and item management
  - Custom field operations
  - Error handling and retry logic with exponential backoff
  - Async/await throughout
- [x] Data models (Issue, AgentClaim, BoardConfig, DependencyGraph)
- [x] BoardConfig with YAML file support
- [x] Comprehensive error handling (BoardNotFoundError, GraphQLError)
- [x] Rate limit monitoring and handling
- [x] Structured logging implementation
- [x] Comprehensive unit tests (44/44 board tests, 85/85 total unit tests passing)
- [x] Documentation structure (INDEX.md, QUICK_START.md, INSTALLATION.md)
- [x] Test reorganization (unit/, integration/, e2e/, tts/)
- [x] Shared fixtures (conftest.py)
- [x] Testing guide (tests/README.md)

**Key Files:**
```
packages/github_ai_agents/src/github_ai_agents/board/
├── __init__.py (49 lines)
├── config.py (185 lines)
├── errors.py (77 lines)
├── manager.py (1,076 lines) ← Core GraphQL client
└── models.py (211 lines)
```

**Commits:**
- `9c4657f` - Initial board module structure
- `565e79c`, `22417f7`, `3f338f1`, `4ab5b1f` - Test suite fixes (100% passing)

---

### Phase 2: Claim System & Dependencies ✅ COMPLETE

**Status:** All functionality implemented and tested (monolithic approach in manager.py)

**Accomplishments:**
- [x] Comment-based claim/release mechanism
  - 24-hour timeout (configurable)
  - Session ID tracking
  - Atomic claim operations via GitHub comments
- [x] Claim renewal (heartbeat) for long-running tasks
  - 1-hour renewal interval (configurable)
  - Extends claim timeout dynamically
- [x] Blocker relationship management
  - add_blocker() - Link blocking dependencies
  - Blocker resolution checking
- [x] Parent-child (epic) relationships
  - mark_discovered_from() - Track work provenance
  - Hierarchical issue tracking
- [x] "Discovered from" tracking
  - Preserves work discovery context
- [x] Dependency graph queries
  - get_dependency_graph() - Complete relationship graph
- [x] Ready work detection algorithm
  - Checks blocker status
  - Respects claim ownership
  - Handles expired claims
- [x] Race condition testing
  - Concurrent claim attempts
  - Claim expiration scenarios
  - Renewal testing
- [x] Comprehensive unit tests (18 new tests added, 62/62 board tests passing)
  - test_claim_work_success
  - test_claim_work_race_condition
  - test_claim_expiration
  - test_claim_renewal
  - test_claim_renewal_wrong_agent
  - test_release_work_completed
  - test_release_work_blocked
  - test_release_work_abandoned
  - test_add_blocker_success
  - test_mark_discovered_from
  - test_get_ready_work_filters_blocked
  - test_get_ready_work_filters_claimed
  - test_get_ready_work_respects_agent_filter
  - test_race_condition_concurrent_claims (2 tests)
  - test_claim_does_not_block_indefinitely (2 tests)

**Implementation Notes:**
- Chose monolithic approach (all in manager.py) rather than separate claims.py/dependencies.py
- Simplifies imports and reduces complexity
- All claim/dependency logic in BoardManager class

**Commits:**
- `22d8290` - Add 18 comprehensive tests for Phase 2

---

### Phase 3: MCP Server ✅ COMPLETE

**Status:** Full MCP server operational with all core tools

**Accomplishments:**
- [x] tools/mcp/github_board/ MCP server implementation
  - GitHubBoardMCPServer class extending BaseMCPServer
  - Port 8021 (following existing MCP server pattern)
  - Async initialization with BoardManager
- [x] 11 core tools implemented:
  1. query_ready_work - Get unblocked, ready-to-work issues
  2. claim_work - Claim an issue for implementation
  3. renew_claim - Renew claim for long-running tasks
  4. release_work - Release claim (completed/blocked/abandoned/error)
  5. update_status - Change issue status (Todo/In Progress/Blocked/Done/Abandoned)
  6. add_blocker - Add blocking dependency
  7. mark_discovered_from - Mark parent-child relationship
  8. get_issue_details - Get full issue context
  9. get_dependency_graph - Get complete dependency graph
  10. list_agents - Get enabled agents
  11. get_board_config - Get current configuration
- [x] HTTP mode support (port 8021) and STDIO mode
- [x] Health checks with board status
- [x] Comprehensive error handling
  - RuntimeError for uninitialized board
  - Graceful degradation patterns
  - Type narrowing for mypy
- [x] Integration with .mcp.json
- [x] Complete MCP server documentation (tools/mcp/github_board/docs/README.md)
  - Tool descriptions and examples
  - Configuration guide
  - Troubleshooting section
- [x] Server testing utility (scripts/test_server.py)

**Key Files:**
```
tools/mcp/github_board/
├── __init__.py
├── server.py (498 lines) ← Main MCP server
├── docs/
│   └── README.md (467 lines)
└── scripts/
    └── test_server.py (112 lines)
```

**Configuration:**
```json
// .mcp.json entry
"github-board": {
  "command": "python",
  "args": ["-m", "tools.mcp.github_board.server", "--mode", "stdio"],
  "env": {
    "GITHUB_TOKEN": "${GITHUB_TOKEN}",
    "GITHUB_REPOSITORY": "${GITHUB_REPOSITORY}",
    "GITHUB_PROJECT_NUMBER": "1"
  }
}
```

**Commits:**
- `2d6989e` - Phase 3 MCP server with 11 core tools

---

### Phase 4: Monitor Integration & GitHub Actions ✅ COMPLETE

**Status:** Full monitor integration with automated board updates

**Accomplishments:**

**Monitor Integration:**
- [x] Updated monitors/issue.py with board integration
  - BoardManager initialization (optional, graceful degradation)
  - Claim work when issue is approved ([Approved][Agent] trigger)
  - Release work when PR is created (reason: "completed")
  - Release work on error (reason: "error")
  - Release work as abandoned if no changes generated
  - Session ID tracking throughout workflow
- [x] Updated monitors/pr.py with board integration
  - BoardManager initialization (optional)
  - Extract issue numbers from PR body (Closes/Fixes/Resolves #N)
  - Update board status to Done when PR is merged
  - Support multiple linked issues per PR
  - Helper methods: _extract_issue_numbers(), _update_board_on_pr_merge()
- [x] Graceful degradation when board config missing
  - No hard dependency on board
  - Logs warnings but continues operation
  - Monitors work normally without board integration

**GitHub Actions:**
- [x] Created .github/workflows/agent-board-integration.yml
  - Trigger on PR merge to update board status
  - Hourly scheduled maintenance task
  - Manual workflow dispatch support
  - Secure env variable handling for PR body (security hardening)
  - Update linked issues to Done when PR merges
  - Self-hosted runner support

**Configuration:**
- [x] Created .github/ai-agents-board.yml
  - Complete board configuration with all settings
  - Project, repository, and field mappings
  - Agent enablement list (claude, opencode, gemini, crush, codex)
  - Work claim settings (24h timeout, 1h renewal)
  - Work queue filters (exclude labels, priority labels)
  - Integration feature toggles
  - Logging and monitoring settings

**Testing:**
- [x] Created test_monitor_board_integration.py (21 tests)
  - TestIssueMonitorBoardIntegration (8 tests)
    - Board manager initialization tests
    - Work claiming tests
    - Work releasing tests (completed, abandoned)
    - Error handling tests
  - TestPRMonitorBoardIntegration (13 tests)
    - Issue number extraction tests (various formats)
    - Board update on PR merge tests
    - Multiple linked issues tests
    - Error handling tests
    - Board manager initialization tests

**Key Features:**
- Optional integration (no breaking changes)
- Proper async/await patterns throughout
- Comprehensive error handling and logging
- Type hints with Optional[BoardManager]
- Security: PR body passed via environment variable

**Key Files:**
```
packages/github_ai_agents/src/github_ai_agents/monitors/
├── issue.py (updated, +84 lines)
└── pr.py (updated, +48 lines)

.github/
├── ai-agents-board.yml (166 lines) ← Board config
└── workflows/
    └── agent-board-integration.yml (137 lines)

packages/github_ai_agents/tests/unit/
└── test_monitor_board_integration.py (239 lines, 21 tests)
```

**Commits:**
- `aefbab7` - Phase 4 monitor and GitHub Actions integration

---

### Phase 5: CLI & Docker (PENDING)

**Status:** Not started - Ready for implementation

**Planned Deliverables:**
- [ ] board/cli.py - CLI tool for human interaction
  - Commands: ready, create, block, status, graph
  - Similar to Beads' `bd` command
  - Argparse-based interface
- [ ] Docker container setup
  - docker/github-board.Dockerfile
  - config/python/requirements-github-board.txt
- [ ] docker-compose integration
  - mcp-github-board service
  - Port 8021 mapping
  - Health checks
  - User permissions
- [ ] End-to-end testing
  - Test full workflow (create → claim → update → release → complete)
  - Multi-agent coordination testing
  - Performance testing (500+ issues)
- [ ] CI/CD pipeline updates
  - .github/workflows/test-github-board.yml
  - Integration with existing test suite

**Reference Implementation:**
See BOARD_INTEGRATION.md Phase 5 section for detailed specifications.

**Estimated Effort:** 4-6 hours

---

### Phase 6: Documentation & Polish (PENDING)

**Status:** Not started - Documentation infrastructure ready

**Planned Deliverables:**

**Documentation:**
- [ ] Complete board integration documentation
  - docs/board-integration.md - User guide
  - docs/board-troubleshooting.md - Common issues
  - docs/board-performance.md - Performance tuning
- [ ] API reference (docs/API_REFERENCE.md)
  - Complete BoardManager API
  - GraphQL query documentation
  - Error handling reference
- [ ] CLI reference (docs/CLI_REFERENCE.md)
  - Command reference
  - Usage examples
  - Configuration options
- [ ] Update CLAUDE.md with board usage examples

**Examples:**
- [ ] examples/multi_agent_example.py
- [ ] examples/custom_agent_example.py
- [ ] examples/github_actions_example.yml
- [ ] examples/security_example.py

**Tooling:**
- [ ] bin/ directory with executable wrappers
  - bin/issue-monitor
  - bin/pr-monitor
  - bin/board-cli
- [ ] bin/README.md

**Package Updates:**
- [ ] Update pyproject.toml
  - Line length: 120 → 127
  - Python requirement: >=3.11
  - Optional dependency groups: [board], [tts], [mcp], [all]
  - Package data patterns

**Reference Implementation:**
See BOARD_INTEGRATION.md Phase 6 section for detailed specifications.

**Estimated Effort:** 6-8 hours

---

## Implementation Summary

### Completed (Phases 1-4)

**Lines of Code:**
- Board module: ~1,600 lines
- MCP server: ~500 lines
- Monitor updates: ~130 lines
- Tests: ~500 lines
- Configuration: ~300 lines
- **Total: ~3,030 lines**

**Test Coverage:**
- Unit tests: 103/103 passing (100%)
  - Board manager: 62 tests
  - Monitor integration: 21 tests
  - Security: 17 tests
  - Agents: 24 tests
- All pre-commit hooks passing

**Commits:**
- Phase 1: `9c4657f`, `565e79c`, `22417f7`, `3f338f1`, `4ab5b1f`
- Phase 2: `22d8290`
- Phase 3: `2d6989e`
- Phase 4: `aefbab7`

### Remaining (Phases 5-6)

**Estimated Total Effort:** 10-14 hours
- Phase 5: 4-6 hours (CLI, Docker, testing)
- Phase 6: 6-8 hours (documentation, examples, tooling)

**Key Blockers:** None - all dependencies resolved

**Next Steps for Future Agent:**
1. Read BOARD_INTEGRATION.md for detailed Phase 5/6 specifications
2. Review existing board/ module and MCP server code
3. Start with Phase 5: board/cli.py implementation
4. Follow existing patterns from monitors and MCP server
5. Ensure all tests pass before moving to Phase 6

---

## Version 0.3.0 - Advanced Features (Planned)

### Multi-Agent Coordination
- [ ] Enhanced board-based work distribution
- [ ] Multi-agent claim coordination
- [ ] Advanced dependency tracking
- [ ] Agent performance metrics

### Documentation Improvements
- [ ] More usage examples
- [ ] Video tutorials (optional)
- [ ] Best practices guide
- [ ] Architecture decision records

### Testing
- [ ] Improve test coverage to >85%
- [ ] Performance testing (500+ issues)
- [ ] Load testing for concurrent agents
- [ ] Integration tests with real GitHub API

---

## Version 0.4.0 - Future Enhancements

### Advanced Board Features
- [ ] Multi-repository board support
- [ ] Cross-repo dependencies
- [ ] Analytics dashboard
- [ ] Custom workflows
- [ ] Workflow templates

### Infrastructure
- [ ] Sphinx documentation generation
- [ ] Package-level docker-compose
- [ ] Performance optimizations
- [ ] Caching layer for GraphQL queries

---

## Backlog

### Technical Debt
- [ ] Async consistency improvements
- [ ] Enhanced error handling
- [ ] Improve logging structure
- [ ] Reduce BoardManager complexity

### Features
- [ ] Slack integration
- [ ] Custom webhook triggers
- [ ] Email notifications
- [ ] Board templates

---

## Notes for Future Agents

### Code Organization
- Board logic is **monolithic** in `manager.py` (Phase 2 decision)
- MCP server follows `BaseMCPServer` pattern
- Monitors have **optional** board integration (graceful degradation)
- All board operations are **async/await**

### Testing Strategy
- Unit tests mock GraphQL responses
- Integration tests require test repository
- All tests use pytest-asyncio
- Fixtures in conftest.py

### Key Design Decisions
1. **Monolithic BoardManager**: Simpler than separate modules
2. **Comment-based claims**: No database required, audit trail in GitHub
3. **24-hour timeout**: Prevents stuck issues, configurable
4. **Optional integration**: Monitors work without board
5. **Security**: PR body via env vars (GitHub Actions hardening)

### Common Pitfalls
- Remember to call `board_manager.initialize()` before operations
- Use `Optional[BoardManager]` type hints
- Handle board unavailability gracefully
- Pass session_id through async call chains
- Don't forget type narrowing for mypy (assert board_manager is not None)

---

**Last Updated:** 2025-10-25
**Branch:** `github-agents-refine`
**Status:** Phases 1-4 Complete, Ready for Phase 5
