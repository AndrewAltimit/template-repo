# Lint Warning Reduction Progress

## Current Status: 136 warnings (down from 168)

Last updated: 2024-12-14

## Remaining Warnings by Category

| Code | Count | Description | Priority | Notes |
|------|-------|-------------|----------|-------|
| W1203 | 70 | logging-fstring-interpolation | Medium | Use `logger.info("msg %s", var)` instead of f-strings |
| W1510 | 18 | subprocess-run-check | Low | Add `check=True` or `check=False` explicitly |
| W1201 | 13 | logging-not-lazy | Medium | Use `%` formatting in logging, not `+` concatenation |
| C0413 | 10 | wrong-import-position | Skip | Intentional pattern for sys.path modifications |
| W0603 | 9 | global-statement | Skip | Intentional singleton pattern |
| W0706 | 4 | try-except-raise | Low | Simplify exception handling |
| W0612 | 3 | unused-variable | High | Easy fix with `_` prefix |
| I1101 | 3 | c-extension-no-member | Skip | False positives from C extensions |
| W0719 | 2 | broad-exception-raised | Medium | Use specific exception types |
| C0302 | 2 | too-many-lines | Low | Consider splitting large modules |
| W0611 | 1 | unused-import | High | Remove unused imports |
| R1732 | 1 | consider-using-with | Low | Use context manager |
| R1723 | 1 | no-else-break | Low | Simplify control flow |
| R1702 | 1 | too-many-nested-blocks | Low | Refactor nested code |
| C2801 | 1 | unnecessary-dunder-call | Low | Use context manager directly |

## Suggested Fix Order

### Session 2: Quick Wins (Est. ~20 warnings)
- [ ] W0612 (3) - Unused variables
- [ ] W0611 (1) - Unused imports
- [ ] W1510 (18) - subprocess.run without check

### Session 3: Logging Fixes Part 1 (Est. ~40 warnings)
- [ ] W1201 (13) - logging-not-lazy
- [ ] W1203 (partial) - logging-fstring-interpolation (pick one file at a time)

### Session 4: Logging Fixes Part 2
- [ ] W1203 (remaining) - Complete f-string to % formatting migration

### Session 5: Code Quality
- [ ] W0706 (4) - try-except-raise
- [ ] W0719 (2) - broad-exception-raised
- [ ] R1732, R1723, R1702, C2801 (4 total) - Minor refactors

### Intentionally Skipped
- C0413 (10) - Import position after sys.path modification is intentional
- W0603 (9) - Global statements for singleton patterns are intentional
- I1101 (3) - C-extension false positives
- C0302 (2) - Large modules may be split later if needed

## Commands

```bash
# Run full lint check
./automation/ci-cd/run-lint-stage.sh full > /tmp/lint-output.txt 2>&1

# Count warnings
grep -oE "\[[A-Z][0-9]+\(" /tmp/lint-output.txt | sort | uniq -c | sort -rn

# Find specific warning type
grep "W1203" /tmp/lint-output.txt

# Find warnings in specific file
grep "mcp_virtual_character" /tmp/lint-output.txt | grep "\[W"
```

## Progress History

| Date | Warnings | Change | Notes |
|------|----------|--------|-------|
| 2024-12-14 | 168 | - | Initial baseline |
| 2024-12-14 | 136 | -32 | Fixed W0612, W0404, W0622, W1514, W1404, C1803 |
