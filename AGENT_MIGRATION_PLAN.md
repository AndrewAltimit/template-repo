# Agent Migration Plan

## Overview
This document outlines the migration plan from `scripts/agents` to the new `packages/github_ai_agents` package.

## Items to Migrate Before Cleanup

### 1. Security Documentation
- [ ] Copy comprehensive security documentation from `scripts/agents/README.md` to `packages/github_ai_agents/docs/security.md`
- [ ] Include all sections on multi-layer security, commit validation, deduplication, etc.

### 2. Subagent System
- [ ] Migrate subagent functionality to `packages/github_ai_agents/src/github_ai_agents/subagents/`
- [ ] Copy role definitions from `scripts/agents/subagents/`
- [ ] Port `SUBAGENTS.md` documentation

### 3. CI/CD Documentation
- [ ] Migrate `AUTONOMOUS_MODE.md` to `packages/github_ai_agents/docs/autonomous_mode.md`
- [ ] Document all agent-specific CLI flags for CI/CD

### 4. Configuration Files
- [ ] Copy `config/mods-config.yml` to `packages/github_ai_agents/configs/`
- [ ] Document configuration options in new package

### 5. Helper Scripts
- [ ] Convert shell scripts to Python CLI commands where appropriate
- [ ] Add installation guide from `install_agents_safe.sh` to documentation

## Items to Reference in New Documentation

### Update CLAUDE.md
Add reference to new package location:
```bash
# Old location (deprecated)
# python3 scripts/agents/run_agents.py

# New location
python3 -m github_ai_agents.cli issue-monitor
```

### Update GitHub Actions
Update all workflows to use new package:
```yaml
# Install new package
- run: pip3 install -e ./github_ai_agents

# Run monitors
- run: python3 -m github_ai_agents.cli issue-monitor
```

## Cleanup Plan

After migration is complete:
1. Add deprecation notice to `scripts/agents/README.md`
2. Update all references in documentation
3. Remove `scripts/agents` directory
4. Update CI/CD workflows

## Timeline
- Phase 1: Migrate documentation (immediate)
- Phase 2: Port missing functionality (1 week)
- Phase 3: Update references (1 week)
- Phase 4: Remove old code (2 weeks)
