# Python to Rust Conversion Roadmap

This document tracks the multi-session effort to convert performance-critical Python components to Rust.

## Status Overview

| Phase | Component | Status | Notes |
|-------|-----------|--------|-------|
| 1a | GitHub Agents CLI | 🟡 In Progress | Simple dispatcher CLI |
| 1b | Code Parser Library | ⬜ Pending | Regex-based code extraction |
| 2a | Markdown Link Checker | ⬜ Pending | Async HTTP validation |
| 2b | PR Monitor Merge | ⬜ Pending | Extend existing Rust pr-monitor |
| 3a | Code Quality MCP | ⬜ Pending | Security-focused subprocess runner |
| 3b | Board Manager CLI | ⬜ Pending | GraphQL client |

## Phase 1: Quick Wins

### 1a: GitHub Agents CLI (`tools/rust/github-agents-cli/`)

**Python Source**: `packages/github_agents/src/github_agents/cli.py` (72 lines)

**Features to implement**:
- `issue-monitor` subcommand with `--continuous` and `--interval` flags
- `pr-monitor` subcommand with `--continuous` flag
- Verbose logging with `-v/--verbose`
- Graceful signal handling (Ctrl+C)

**Design Decision**: The Rust CLI will be a thin wrapper that delegates to the Python monitors initially. This gives us:
- Fast startup (Rust binary)
- Single binary distribution
- Foundation for future pure-Rust implementation

### 1b: Code Parser Library (`tools/rust/code-parser/`)

**Python Source**: `packages/github_agents/src/github_agents/code_parser.py` (292 lines)

**Features to implement**:
- `extract_code_blocks()` - Parse markdown code blocks with language detection
- `apply_code_blocks()` - Write extracted code to files with security checks
- `sanitize_filename()` - Path traversal prevention
- `infer_language()` - Extension-to-language mapping
- `parse_edit_instructions()` - Parse "change X to Y" instructions

**Rust Advantages**:
- Memory-safe regex parsing
- Better path handling with `std::path`
- Type-safe API for embeddings

## Phase 2: High Impact

### 2a: Markdown Link Checker (`tools/rust/markdown-link-checker/`)

**Python Source**: `tools/cli/utilities/markdown_link_checker.py` (247 lines)

**Features**:
- Recursive markdown file discovery
- Link extraction via markdown parser
- Concurrent HTTP validation
- Configurable ignore patterns
- JSON output for CI integration

**Rust Advantages**:
- Faster HTTP client (reqwest)
- Better async performance with tokio
- Lower memory footprint for large codebases

### 2b: PR Monitor Enhancement

**Approach**: Extend `tools/rust/pr-monitor/` with features from Python `monitors/pr.py`:
- Gemini review detection patterns
- Codex review detection patterns
- Commit SHA extraction
- Response marker tracking

## Phase 3: Infrastructure

### 3a: Code Quality MCP Server

**Python Source**: `tools/mcp/mcp_code_quality/` (1,209 lines)

**Key Operations**:
- Subprocess execution with timeouts
- Path validation and security
- Rate limiting
- Audit logging

### 3b: Board Manager CLI

**Python Source**: `packages/github_agents/src/github_agents/board/` (1,663+ lines)

**Key Operations**:
- GitHub Projects v2 GraphQL API
- Work claim/release coordination
- Dependency graph management

## Completed Items

_None yet - tracking will be updated as phases complete._

## Session Log

### Session 1 (Current)
- Created branch `feat/rust-conversion-phase1-3`
- Analyzed Python sources for conversion scope
- Created this roadmap document
- Starting Phase 1a: GitHub Agents CLI
