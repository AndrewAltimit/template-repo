# Multi-Agent System Migration Status

This document tracks the migration from the scripts-based agent system to the new `github_ai_agents` package.

## Migration Philosophy

We are following a **phased migration approach** to ensure stability:

1. **Phase 1**: Create new package structure alongside existing scripts
2. **Phase 2**: Migrate workflows one by one to use new package
3. **Phase 3**: Keep old scripts as reference for security patterns and documentation
4. **Phase 4**: Eventually archive old scripts once fully stable

## Current Status (as of this PR)

### ✅ Migrated to New Package

- **Issue Monitor** - Using `python3 -m github_ai_agents.cli issue-monitor`
- **PR Review Monitor** - Using `python3 -m github_ai_agents.cli pr-monitor`

### 📚 Retained for Reference

The `scripts/agents/` directory contains:
- **Security implementation patterns** - Comprehensive security documentation
- **Legacy integration examples** - Shows how agents were originally structured
- **Direct CLI usage** - For local development and testing

## Why Keep Both?

1. **Documentation Value**: The scripts contain extensive security documentation and implementation patterns that serve as a reference.

2. **Backward Compatibility**: External tools or documentation may reference the old paths.

3. **Local Development**: The scripts provide examples for developers who want to run agents locally without the package.

4. **Audit Trail**: Maintains the evolution of our security model and implementation approach.

## Not a Dual Implementation

This is **not** a dual implementation issue. The scripts and package serve different purposes:

- **Package (`github_ai_agents`)**: Production implementation used by GitHub Actions
- **Scripts (`scripts/agents/`)**: Reference implementation and documentation

The package is the canonical implementation. The scripts are retained for their documentation value and historical context.
