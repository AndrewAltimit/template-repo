# Rust Migration: github_agents Package

This document tracks the migration of `packages/github_agents` Python package to Rust.

## Current Status

**Target:** Fully replace Python `github_agents` with Rust implementation
**Tracking PR:** TBD

## Completed (in board-manager)

| Module | Python LOC | Rust Location | Status |
|--------|------------|---------------|--------|
| `security/trust.py` | 271 | `board-manager/src/security/trust.rs` | DONE |
| `security/judgement.py` | 607 | `board-manager/src/security/judgement.rs` | DONE |
| `board/manager.py` | 1,663 | `board-manager/src/manager.rs` | DONE |
| `board/models.py` | 303 | `board-manager/src/models.rs` | DONE |
| `board/config.py` | 225 | `board-manager/src/config.rs` | DONE |
| `board/errors.py` | 68 | `board-manager/src/error.rs` | DONE |
| `board/cli.py` | 821 | `board-manager/src/cli.rs` | DONE |

**Subtotal:** ~3,958 LOC completed

## Phase 1: Core Infrastructure (Priority: CRITICAL)

| Module | Python LOC | Rust Location | Status |
|--------|------------|---------------|--------|
| `utils/github.py` | 158 | `github-agents-cli/src/utils/github.rs` | DONE |
| `config.py` | 170 | `github-agents-cli/src/config.rs` | TODO |
| `code_parser.py` | 291 | Already have `code-parser` crate | DONE |

## Phase 2: Security Manager (Priority: HIGH)

| Module | Python LOC | Rust Location | Status |
|--------|------------|---------------|--------|
| `security/manager.py` | 450 | `github-agents-cli/src/security/manager.rs` | DONE |

## Phase 3: Agent Infrastructure (Priority: HIGH)

| Module | Python LOC | Rust Location | Status |
|--------|------------|---------------|--------|
| `agents/base.py` | 209 | `github-agents-cli/src/agents/base.rs` | DONE |
| `agents/cli.rs` | - | `github-agents-cli/src/agents/cli.rs` | DONE (new) |
| `agents/registry.rs` | - | `github-agents-cli/src/agents/registry.rs` | DONE (new) |
| `agents/containerized.py` | 217 | Merged into cli.rs | DONE |
| `agents/claude.py` | 44 | Merged into cli.rs | DONE |
| `agents/gemini.py` | 86 | Merged into cli.rs | DONE |
| `agents/opencode.py` | 205 | Merged into cli.rs | DONE |
| `agents/crush.py` | 96 | Merged into cli.rs | DONE |
| `agents/codex.py` | 290 | Merged into cli.rs | DONE |

**Note:** All agent implementations are unified in `cli.rs` with agent-specific execution
methods (Claude, Gemini, Codex, OpenCode, Crush) that match the Python CLI interfaces.

## Phase 4: Monitoring (Priority: MEDIUM)

| Module | Python LOC | Rust Location | Status |
|--------|------------|---------------|--------|
| `monitors/base.py` | 376 | `github-agents-cli/src/monitor/base.rs` | DONE |
| `monitors/issue.py` | 754 | `github-agents-cli/src/monitor/issue.rs` | DONE |
| `monitors/pr.py` | 1,880 | `github-agents-cli/src/monitor/pr.rs` | DONE |
| `monitors/refinement.py` | 1,150 | `github-agents-cli/src/monitor/refinement.rs` | DONE |

**Note:** All monitors now have full agent integration:
- **IssueMonitor & PrMonitor**: Auto-select agents, execute implementations, perform reviews
- **RefinementMonitor**: Multi-agent backlog refinement with:
  - Agent-specific prompts (architectural, quality/security, implementation, maintainability)
  - Cooldown system to prevent duplicate insights (14 days default)
  - Fingerprinting for deduplication
  - Configurable age filters and label exclusions

## Phase 5: Creators & Analyzers (Priority: LOW)

| Module | Python LOC | Rust Location | Status |
|--------|------------|---------------|--------|
| `analyzers/base.py` | 522 | `github-agents-cli/src/analyzers/base.rs` | DONE |
| `creators/issue_creator.py` | 477 | `github-agents-cli/src/creators/issue.rs` | DONE |
| `subagents/manager.py` | 217 | `github-agents-cli/src/subagents/manager.rs` | TODO |

**Note:** Analyzers and creators are fully ported:
- **AgentAnalyzer**: AI-powered codebase analysis with file collection, content limits, and response parsing
- **IssueCreator**: Issue creation with fingerprint-based deduplication, label management, and board integration via board-manager CLI
- Finding types: FindingCategory, FindingPriority, AffectedFile, AnalysisFinding with fingerprinting

**Board Integration:** IssueCreator calls board-manager CLI to add issues to the project board with priority, type, size, and agent fields.

## Phase 6: Optional Features (Priority: OPTIONAL)

| Module | Python LOC | Decision |
|--------|------------|----------|
| `memory/` | 561 | Keep in Python (MCP server integration) |
| `tts/` | 1,228 | Keep in Python (ElevenLabs SDK) |

## Architecture

```
tools/rust/
├── board-manager/          # Board operations (DONE)
│   └── src/
│       ├── security/       # Trust + Judgement
│       ├── manager.rs      # Board GraphQL client
│       └── cli.rs          # Board CLI
│
├── github-agents-cli/      # Agent coordination (NEW)
│   └── src/
│       ├── agents/         # Agent implementations
│       ├── monitors/       # Issue/PR monitoring
│       ├── security/       # Security manager
│       ├── analyzers/      # Code analysis
│       ├── creators/       # Issue creation
│       └── utils/          # GitHub CLI wrappers
│
└── code-parser/            # Code parsing library (DONE)
```

## Rust Crates Required

```toml
[dependencies]
tokio = { version = "1", features = ["full"] }
async-trait = "0.1"
reqwest = { version = "0.12", features = ["json"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yaml = "0.9"
clap = { version = "4", features = ["derive"] }
anyhow = "1"
thiserror = "1"
tracing = "0.1"
tracing-subscriber = "0.3"
regex = "1"
chrono = { version = "0.4", features = ["serde"] }
lazy_static = "1"
```

## Migration Notes

### Approach
1. Create new `github-agents-cli` crate
2. Port modules in dependency order (utils -> security -> agents -> monitors)
3. Share code with `board-manager` via workspace
4. Update workflows to use Rust binaries
5. Deprecate Python package after validation

### Testing Strategy
- Unit tests for each module
- Integration tests against GitHub API (mocked)
- E2E tests with real GitHub repos (CI only)
- Parallel Python/Rust runs for validation

### Rollout Plan
1. Deploy Rust binaries alongside Python
2. Gradually switch workflows to Rust
3. Monitor for issues
4. Remove Python package after 2 weeks stability
