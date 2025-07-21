# Auto-Formatting Git Commits

This directory contains scripts to help automatically stage files that are reformatted by pre-commit hooks (black, isort, etc.).

## Problem

When pre-commit hooks reformat your code, the commit fails because files have been modified. You then need to stage the changes and commit again, which is tedious.

## Solutions

We provide two approaches to solve this:

### Option 1: Git Hook (Recommended)

Install a custom git pre-commit hook that automatically stages formatted files:

```bash
./scripts/install-auto-format-hook.sh
```

This replaces the default pre-commit hook with one that:
1. Runs formatters (black, isort, etc.)
2. Auto-stages any formatting changes
3. Re-runs validation
4. Allows the commit if all checks pass

To uninstall: `rm .git/hooks/pre-commit`

### Option 2: Git Alias

Set up a git alias `cf` (commit formatted):

```bash
./scripts/setup-git-commit-alias.sh
```

Then use:
```bash
git cf -m "Your commit message"    # Auto-formats and commits
git commit -m "Message"            # Regular commit (no auto-staging)
```

## Which to Choose?

- **Git Hook**: Seamless experience, works with regular `git commit`
- **Git Alias**: More explicit control, preserves original commit behavior

Both approaches ensure that formatting changes are automatically staged and don't block your commits.

## Manual Approach

If you prefer not to use either automation:

```bash
# When commit fails due to formatting
git add -u                # Stage the formatted files
git commit               # Retry the commit
```
