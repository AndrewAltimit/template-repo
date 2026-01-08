# Gemini Auto-Response System

This document describes the automatic response system for AI code review feedback in the GitHub Agents package.

## Overview

The PR Review Monitor now includes an **auto-response** capability that automatically processes Gemini AI review feedback without requiring explicit trigger keywords from authorized users.

### Two Modes of Operation

1. **Trigger-Based Mode** (Original)
   - Requires explicit `[Approved][Agent]` keyword from authorized users
   - Full security validation via allow-list
   - Manual control over when agents act

2. **Auto-Response Mode** (New)
   - Automatically detects Gemini review comments
   - Uses AgentJudgement system to assess confidence
   - High-confidence issues are auto-fixed
   - Low-confidence issues trigger "Ask Owner" flow

## How It Works

### 1. Gemini Review Detection

The system identifies Gemini review comments by checking:
- Comment author is `github-actions[bot]`
- Comment body matches Gemini review patterns (e.g., "## Code Review", "Gemini AI Review")

### 2. Actionable Item Extraction

From each Gemini review, the system extracts actionable items:
- Numbered lists (1. Issue description)
- Bullet points (- Issue description)
- Headers with issue keywords (### Fix Required)

### 3. Confidence Assessment

Each actionable item is assessed using the `AgentJudgement` system:

#### High Confidence (Auto-Fix)
- Security vulnerabilities
- Syntax errors
- Type errors
- Import errors
- Formatting issues
- Linting violations
- Unused imports/variables

#### Medium Confidence (Context-Dependent)
- Error handling improvements
- Null checks
- Documentation updates
- Test coverage
- Performance optimizations

#### Low Confidence (Ask Owner)
- Architectural changes
- API changes
- Breaking changes
- Data model modifications
- Business logic changes
- Dependency updates
- Multiple valid approaches

### 4. Action Execution

Based on confidence assessment:

**Auto-Fix Path:**
1. Post "Starting work" comment
2. Generate fixes using configured agent (default: Claude)
3. Apply code changes
4. Commit and push
5. Post completion comment

**Ask Owner Path:**
1. Post comment requesting guidance
2. List items needing decision
3. Provide options for owner to choose
4. Wait for `[Approved]` trigger to proceed

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISABLE_GEMINI_AUTO_RESPONSE` | `false` | Set to `true` to disable auto-response |

### Agent Configuration

The system uses agent priorities from `.agents.yaml`:

```yaml
agent_priorities:
  code_fixes:
    - claude      # Primary agent for implementing fixes
    - opencode    # Fallback option
```

### Security Settings

Auto-response respects the same security model:
- Only responds to PRs in allowed repositories
- Uses configured agent tokens
- Masks secrets in comments

## Response Tracking

The system tracks responses using hidden HTML markers:

```html
<!-- ai-agent-gemini-response:2026-01-08-12-34-56-IC_123456 -->
```

This prevents duplicate responses to the same Gemini review.

## Example Flow

### Scenario: Gemini identifies a security issue and formatting problem

1. **Gemini Review Posted:**
   ```markdown
   ## Code Review

   1. SQL injection vulnerability in `query_user()` - user input not sanitized
   2. Line too long in `process_data.py:45` (exceeds 120 characters)
   ```

2. **AgentJudgement Assessment:**
   - Item 1: Security vulnerability (confidence: 95%, auto-fix)
   - Item 2: Formatting (confidence: 85%, auto-fix)

3. **Auto-Fix Execution:**
   - Posts "Automatically addressing..." comment
   - Claude generates fixes
   - Commits: "fix: address Gemini review feedback"
   - Posts completion comment

### Scenario: Gemini suggests architectural change

1. **Gemini Review Posted:**
   ```markdown
   ## Code Review

   Consider refactoring this module to use the repository pattern
   for better separation of concerns.
   ```

2. **AgentJudgement Assessment:**
   - Item: Architectural change (confidence: 30%, ask owner)

3. **Ask Owner Flow:**
   - Posts comment with options
   - Waits for owner guidance
   - Owner replies `[Approved]` to proceed

## Disabling Auto-Response

### Per-Workflow Run

Use the workflow dispatch input:

```yaml
- name: disable_gemini_auto_response
  type: boolean
  default: false
```

### Permanently

Set environment variable in workflow:

```yaml
env:
  DISABLE_GEMINI_AUTO_RESPONSE: "true"
```

Or in repository variables:

```
vars.DISABLE_GEMINI_AUTO_RESPONSE = true
```

## Troubleshooting

### Auto-response not triggering

1. Check if `DISABLE_GEMINI_AUTO_RESPONSE` is set
2. Verify comment is from `github-actions[bot]`
3. Check if review matches Gemini patterns
4. Look for existing response markers

### Duplicate responses

The system should prevent duplicates via markers. If duplicates occur:
1. Check marker format in comments
2. Verify timestamp extraction is working
3. Check for race conditions in parallel runs

### Wrong confidence assessment

The `AgentJudgement` system uses pattern matching. To improve:
1. Review patterns in `security/judgement.py`
2. Add new patterns for specific categories
3. Adjust confidence thresholds

## Related Documentation

- [PR Monitoring](pr-monitoring.md) - General PR monitoring guide
- [Security](security.md) - Security model documentation
- [Agent Configuration](../integrations/ai-services/ai-code-agents.md) - Agent setup
