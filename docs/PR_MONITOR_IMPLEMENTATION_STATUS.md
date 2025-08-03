# PR Monitor Implementation Status

This document clarifies the current implementation status of the PR Monitor's review feedback functionality.

## Current State

The PR Monitor (`github_ai_agents.monitors.pr`) has been fully implemented with the following capabilities:

1. ✅ **PR Detection**: Monitors open PRs for review feedback and comments
2. ✅ **Trigger Recognition**: Detects `[ACTION][AGENT]` commands in reviews/comments
3. ✅ **Multi-Agent Support**: Works with any configured agent (Claude, Gemini, OpenCode, Codex, Crush)
4. ✅ **Security Validation**: Checks user authorization and rate limits
5. ✅ **Agent Selection**: Routes to appropriate agent based on trigger
6. ✅ **Code Generation**: Calls AI agent to generate fixes
7. ⚠️  **Fix Application**: Currently posts a comment only (intentional MVP)

## Trigger Command Format

The PR monitor looks for commands in the format `[ACTION][AGENT]` where:

- **ACTION**: Fix, Address, Implement (case-insensitive)
- **AGENT**: Claude, Gemini, OpenCode, Codex, Crush, etc.

Examples:
- `[Fix][Claude]` - Use Claude to fix the issue
- `[Address][Gemini]` - Use Gemini to address the feedback
- `[Implement][OpenCode]` - Use OpenCode to implement the changes

## Why Fix Application is Minimal

Similar to the Issue Monitor, the PR Monitor intentionally only posts a comment instead of applying fixes directly. This is because:

1. **Security First**: Validate the agent system's security model before allowing automated commits to PR branches
2. **Review Workflow**: Many teams prefer to review AI-generated fixes before they're committed
3. **Branch Protection**: PR branches often have protection rules that would block automated commits
4. **Maintainer Control**: Allows maintainers to review and selectively apply suggested fixes

## Implementation Details

The PR Monitor implementation includes:

- Full review comment parsing (both PR reviews and issue comments)
- PR diff retrieval to provide context to agents
- Support for multiple agents with proper error handling
- Clear messaging when containerized agents are requested on host
- Tracking to avoid duplicate responses to the same review

## Future Implementation Plan

### Phase 1 (Current)
- Agent generates fix implementation
- Posts comment with proposed solution
- No actual code changes to PR branch

### Phase 2 (Next)
- Create commits on PR branch with generated fixes
- Support for selective application of fixes
- Integration with CI/CD to verify fixes don't break tests

### Phase 3 (Future)
- Automatic PR undrafting when all feedback is addressed
- Pipeline failure detection and automatic fixes
- Multi-round conversation support for complex reviews

## Using the Current System

Even without automatic fix application, the PR Monitor is useful for:
- Getting AI-generated solutions to review feedback
- Testing multi-agent capabilities on real reviews
- Validating the security model
- Gathering implementation suggestions

The comment-based approach allows maintainers to manually apply the suggested fixes when appropriate, maintaining full control over the codebase.

## Agent Availability

Note that when running on the host (required for Claude authentication), only host-compatible agents are available:
- Claude (requires subscription auth)
- Gemini (requires Docker access)

Containerized agents (OpenCode, Codex, Crush) are only available when the monitor runs in the `openrouter-agents` container.
