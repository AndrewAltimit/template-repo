# Lint Warning Reduction Progress

## Current Status: 24 warnings (down from 168) - ALL REMAINING INTENTIONAL

Last updated: 2025-12-14

## Remaining Warnings by Category

| Code | Count | Description | Status | Notes |
|------|-------|-------------|--------|-------|
| C0413 | 10 | wrong-import-position | Skip | Intentional pattern for sys.path modifications |
| W0603 | 9 | global-statement | Skip | Intentional singleton pattern |
| I1101 | 3 | c-extension-no-member | Skip | False positives from C extensions |
| C0302 | 2 | too-many-lines | Skip | Large modules, optional future refactor |

## Suggested Fix Order

### Session 2: Quick Wins - COMPLETED
- [x] W0612 (3) - Unused variables - renamed with `_` prefix
- [x] W0611 (1) - Unused imports - added pylint disable
- [x] W1510 (18) - subprocess.run without check - added `check=False`
- [x] W0706 (4) - try-except-raise - removed redundant handlers
- [x] W0719 (2) - broad-exception-raised - use RuntimeError

### Session 3: Logging Fixes - COMPLETED
- [x] W1201 (13) - logging-not-lazy - converted to % formatting
- [x] W1203 (70) - logging-fstring-interpolation - converted to % formatting
- [x] W0706 (3) - try-except-raise - moved pylint disable to except line

### Session 4: Minor Refactors - COMPLETED
- [x] R1732 (1) - consider-using-with - added pylint disable (fire-and-forget pattern)
- [x] R1723 (1) - no-else-break - changed elif to if after break
- [x] R1702 (1) - too-many-nested-blocks - early continue + walrus operator
- [x] C2801 (1) - unnecessary-dunder-call - added pylint disable (lazy init pattern)

### Intentionally Skipped
- C0413 (10) - Import position after sys.path modification is intentional
- W0603 (9) - Global statements for singleton patterns are intentional
- I1101 (3) - C-extension false positives
- C0302 (2) - Large modules may be split later if needed

## CI/CD Enforcement

The lint baseline is now **enforced in PR validation**. Any PR that introduces new warnings will fail the `full-lint` check.

### How It Works

1. **Baseline file**: `config/lint/pylint-baseline.json` defines allowed warning counts by category
2. **Regression check**: `automation/ci-cd/check-lint-baseline.py` compares current warnings to baseline
3. **PR validation**: The `full-lint` stage in `lint-stages.yml` fails if warnings exceed baseline

### What Triggers a Failure

- **New warning type**: Any pylint code not in the baseline (e.g., introducing `W0612`)
- **Increased count**: More warnings of an existing type than baseline allows
- **Total exceeded**: Total warnings greater than `total_allowed` (currently 24)

### Adding a New Intentional Warning

If you need to add a new intentional warning:

1. Update `config/lint/pylint-baseline.json` with:
   - The warning code and count
   - Description of the warning
   - Justification for why it's intentional
2. Update the `total_allowed` count
3. Document in this file under "Intentionally Skipped"

### Commands

```bash
# Run full lint check
./automation/ci-cd/run-lint-stage.sh full > /tmp/lint-output.txt 2>&1

# Count warnings
grep -oE "\[[A-Z][0-9]+\(" /tmp/lint-output.txt | sort | uniq -c | sort -rn

# Check against baseline manually
python automation/ci-cd/check-lint-baseline.py /tmp/lint-output.txt

# Find specific warning type
grep "W1203" /tmp/lint-output.txt

# Find warnings in specific file
grep "mcp_virtual_character" /tmp/lint-output.txt | grep "\[W"
```

## Progress History

| Date | Warnings | Change | Notes |
|------|----------|--------|-------|
| 2025-12-14 | 168 | - | Initial baseline |
| 2025-12-14 | 136 | -32 | Session 1: Fixed W0612, W0404, W0622, W1514, W1404, C1803 |
| 2025-12-14 | ~102 | -34 | Session 2: Fixed W0612(3), W0611(1), W1510(18), W0706(4), W0719(2) |
| 2025-12-14 | ~28 | -74 | Session 3: Fixed W1201(13), W1203(70+3), W0706(3 via pylint comment) |
| 2025-12-14 | 24 | -4 | Session 4: Fixed R1732, R1723, R1702, C2801 - ALL REMAINING INTENTIONAL |
