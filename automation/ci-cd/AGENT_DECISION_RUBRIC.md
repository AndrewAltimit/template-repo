# Agent Review Response Decision Rubric

This document defines the decision-making framework for the automated agent
review response system. The agent uses this rubric to determine when to act,
when to skip, and when to escalate to human admins.

## Core Principles

1. **Never Treat AI Feedback as Ground Truth**: AI reviewers (Gemini, Codex)
   can and do hallucinate. Every reported issue must be validated before action.

2. **Validate Before Acting**: Static analysis, file existence checks, and
   pattern matching must confirm an issue is real before attempting fixes.

3. **Minimize False Positive Actions**: It's better to skip a real issue than
   to make incorrect changes based on hallucinated feedback.

4. **Escalate Sparingly**: Admin escalation should only occur for genuinely
   ambiguous situations requiring human judgment.

## Source Classification

Sources are classified based on `.agents.yaml` configuration:

### 1. Agent Admins (`security.agent_admins`)
- **Who**: Repository owner (AndrewAltimit)
- **Trust Level**: HIGH
- **Can**: Approve agent actions, override decisions
- **Treatment**: Directives should be followed, but still validate technical claims

### 2. Trusted Sources (`security.trusted_sources`)
- **Who**: Admins + GitHub Actions bot, Dependabot, Renovate
- **Trust Level**: MEDIUM
- **Can**: Provide context, suggestions considered seriously
- **Treatment**: Validate claims, act on clearly correct feedback

### 3. AI Reviewers (Gemini, Codex, etc.)
- **Trust Level**: LOW (hallucination-prone)
- **Treatment**: ALWAYS validate, never treat as ground truth
- **Known Issues**:
  - Report bugs in code that doesn't exist
  - Misidentify file paths or line numbers
  - Flag correct code as incorrect
  - Suggest unnecessary changes

### 4. Untrusted Sources (Everyone else)
- **Trust Level**: MINIMAL
- **Treatment**: Only act on clearly verifiable issues

## Feedback Type Classification

### Type A: Clear Bugs/Errors (AUTO-FIX if validated)
Characteristics:
- Syntax errors, undefined variables, missing imports
- Can be verified by static analysis or grep
- Fix is mechanical and obvious

Examples:
- `import os` missing but `os.path` used
- Undefined variable referenced
- Obvious typo in function name

**Action**: Validate → Fix regardless of source

### Type B: Style/Formatting (AUTO-FIX)
Characteristics:
- Indentation, spacing, line length
- Consistent with project standards (black, isort)
- No logic changes involved

Examples:
- Wrong indentation level
- Missing trailing newline
- Import order issues

**Action**: Run autoformat tools, fix if they make changes

### Type C: Debatable Suggestions (SKIP or ESCALATE)
Characteristics:
- Could be argued either way
- Involves architectural decisions
- Changes public API or behavior

Examples:
- "Consider using a different algorithm"
- "This could be refactored to..."
- "You might want to add error handling for..."

**Action**: Skip from AI/untrusted sources. Consider from admin.

### Type D: Tool/Dependency Changes (ALWAYS ESCALATE)
Characteristics:
- Adding or removing dependencies
- Changing build tools or configuration
- Modifying CI/CD pipelines

Examples:
- "Add pytest-cov for coverage"
- "Switch from requests to httpx"
- "Update the workflow to use..."

**Action**: NEVER auto-act. Always escalate to admin.

## Decision Matrix

| Feedback Type | Admin | Trusted | AI Reviewer | Untrusted |
|--------------|-------|---------|-------------|-----------|
| Clear Bug (validated) | Fix | Fix | Fix | Fix |
| Clear Bug (unvalidated) | Validate→Fix | Validate→Fix | Skip | Skip |
| Style/Formatting | Fix | Fix | Fix | Fix |
| Debatable | Consider | Skip | Skip | Skip |
| Tool/Dep Change | Escalate | Escalate | Skip | Skip |

## Validation Requirements

Before acting on any reported bug:

### 1. File Existence Check
```bash
# Verify the file mentioned actually exists
[ -f "$reported_file" ] || skip "File does not exist"
```

### 2. Line Number Validation
```bash
# Verify line numbers are within file bounds
total_lines=$(wc -l < "$file")
[ "$reported_line" -le "$total_lines" ] || skip "Line number out of range"
```

### 3. Pattern Confirmation
```bash
# Verify the reported issue pattern exists in the file
grep -q "$issue_pattern" "$file" || skip "Pattern not found in file"
```

### 4. Static Analysis Confirmation
```bash
# For import issues, verify with actual linting
flake8 "$file" | grep -q "F401\|F811" || skip "Linter doesn't confirm issue"
```

## Escalation Triggers

The agent should post an escalation comment when:

1. **Tool/Dependency Changes Requested**
   - Any suggestion to add, remove, or update dependencies
   - Changes to build configuration or CI/CD

2. **Conflicting Feedback**
   - Multiple AI reviewers give contradictory suggestions
   - Feedback conflicts with existing code style

3. **Unclear Impact**
   - Cannot determine if fix is safe
   - Change might affect other parts of codebase

4. **Breaking Change Risk**
   - Fix might change public API behavior
   - Test failures might result

### Escalation Comment Format
```markdown
## Agent Escalation Request

**Reason**: [Why escalation is needed]

**Feedback Received**:
[Quote the feedback]

**Agent Assessment**:
[Why the agent is uncertain]

**Options**:
1. [Option A]
2. [Option B]
3. Ignore this feedback

@AndrewAltimit Please advise on how to proceed.

_This escalation is from the automated review agent._
```

## Implementation Notes

### Pattern Matching for Feedback Types

**Clear Bug Indicators**:
- `undefined`, `not defined`, `NameError`
- `import.*not found`, `missing import`
- `syntax error`, `SyntaxError`
- `unused import`, `F401`

**Debatable Suggestion Indicators**:
- `consider`, `might want`, `could be`
- `suggest`, `recommend`, `perhaps`
- `refactor`, `restructure`, `redesign`

**Tool/Dependency Indicators**:
- `add.*dependency`, `install.*package`
- `upgrade`, `update.*version`
- `switch.*to`, `replace.*with`
- `workflow`, `pipeline`, `CI/CD`

### Source Detection

Review comments include author information:
- Check comment metadata for author username
- Match against `agent_admins` and `trusted_sources` from `.agents.yaml`
- AI reviewers are identified by their marker comments (e.g., "Gemini AI Review")

## Examples

### Example 1: Valid Bug from AI Reviewer
```
Feedback: "[BUG] Line 45: `import os` is missing but `os.path.join` is used"
Validation: grep -n "os.path" file.py → Found at line 45
            grep -n "import os" file.py → NOT FOUND
Action: FIX (validation confirmed the issue)
```

### Example 2: Hallucinated Bug from AI Reviewer
```
Feedback: "[BUG] Line 120: undefined variable `config`"
Validation: File only has 80 lines
Action: SKIP (line number invalid, likely hallucination)
```

### Example 3: Debatable Suggestion from Untrusted Source
```
Feedback: "You should use async/await here for better performance"
Source: Random commenter
Action: SKIP (debatable suggestion from untrusted source)
```

### Example 4: Tool Change from Admin
```
Feedback: "Add mypy for type checking in CI"
Source: AndrewAltimit (admin)
Action: ESCALATE (tool change requires explicit approval even from admin)
```
