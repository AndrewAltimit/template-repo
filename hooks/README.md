# Git Hooks

This directory contains Git hooks for this repository.

## Installing the pre-commit hook

To use the pre-commit hook that automatically restages formatted files:

```bash
# Make the hooks directory executable
chmod +x hooks/pre-commit

# Create a symbolic link from .git/hooks to our hooks directory
ln -sf ../../hooks/pre-commit .git/hooks/pre-commit
```

Alternatively, you can copy the hook directly:

```bash
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## What the pre-commit hook does

- Runs pre-commit checks (formatting, linting, etc.)
- If files are reformatted, it automatically restages ONLY the files that were already staged
- Prevents accidentally staging new files during the auto-format process
- Runs the checks again after restaging to ensure everything passes

## Notes

- Git hooks are local to each repository clone
- Each developer needs to install the hook manually
- The hook requires `pre-commit` to be installed and configured
