# Agent Templates

This directory contains template scripts for AI agent operations.

## Legacy Scripts (Deprecated)

The following shell scripts are legacy implementations that have been replaced by the Claude Code subagent system:

- `implement_test_feature.sh` - Previously used by issue_monitor.py
- `fix_pr_review.sh` - Previously used by pr_review_monitor.py
- `fix_pipeline_failure.sh` - Used for fixing CI/CD pipeline failures

## New Subagent System

The AI agents now use Claude Code with specialized personas instead of shell scripts:

### For Issue Implementation
```python
from subagent_manager import implement_issue_with_tech_lead

# The issue_monitor.py now uses:
success, output = implement_issue_with_tech_lead(issue_data, branch_name)
```

### For PR Review Fixes
```python
from subagent_manager import review_pr_with_qa

# The pr_review_monitor.py now uses:
success, output = review_pr_with_qa(pr_data, review_comments)
```

### Available Personas

1. **tech-lead** - For implementing features from issues
   - Architecture-first approach
   - Clean, maintainable code
   - Comprehensive testing
   - Documentation updates

2. **qa-reviewer** - For addressing PR review feedback
   - Security-focused reviews
   - Code quality checks
   - Performance considerations
   - Maintainability analysis

3. **security-auditor** - For deep security analysis
   - AI-specific attack vectors
   - Traditional vulnerabilities
   - Container security
   - Compliance checks

## Using the Subagent CLI

You can also use the Claude Code subagents directly via the CLI:

```bash
# Implement an issue
python ../claude_subagent.py tech-lead implement --issue 123 --repo owner/repo

# Review a PR
python ../claude_subagent.py qa-reviewer review --pr 456 --repo owner/repo

# Security audit
python ../claude_subagent.py security-auditor audit --path /path/to/code

# Custom task
python ../claude_subagent.py tech-lead custom --task "Refactor authentication module"
```

## Migration Guide

If you have scripts that depend on the old shell script templates:

1. **Update to use SubagentManager directly:**
   ```python
   from subagent_manager import SubagentManager

   manager = SubagentManager()
   success, output = manager.execute_with_persona(
       "tech-lead",
       task_description,
       context_dict
   )
   ```

2. **Or use the convenience functions:**
   - `implement_issue_with_tech_lead()` for issue implementation
   - `review_pr_with_qa()` for PR review fixes

3. **The shell scripts remain for reference but are no longer actively used**

## Benefits of the New System

1. **Specialized Personas**: Each agent has specific expertise and focus
2. **Better Context**: Claude Code understands the full project context
3. **Improved Quality**: More thorough analysis and implementation
4. **Flexibility**: Easy to add new personas or modify existing ones
5. **Consistency**: All agents use the same underlying system

For more details, see the subagent documentation in `../subagents/`.
