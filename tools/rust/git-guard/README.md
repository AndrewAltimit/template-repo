# git-guard

A Git CLI wrapper that blocks dangerous operations like force push, `--no-verify`, and direct pushes to protected branches (`main`/`master`).

## Purpose

AI coding assistants (like Claude Code) may sometimes attempt force pushes, skip verification hooks, or push directly to protected branches during automated workflows. This wrapper blocks these operations entirely to ensure code review workflows are followed.

## Blocked Operations

The following operations are blocked:

### Force Push (on `git push` only)
- `--force` / `-f`
- `--force-with-lease`
- `--force-if-includes`

### Skip Hooks
- `--no-verify` (on any command)
- `-n` (only on `commit`, `merge`, `cherry-pick`, `revert` where it means `--no-verify`)

### Push to Protected Branches
- `git push origin main` - Direct push to `main` branch
- `git push origin master` - Direct push to `master` branch
- `git push origin HEAD:main` - Push via refspec to protected branch

This ensures all changes to `main`/`master` go through pull requests, preventing AI agents from accidentally pushing directly to protected branches.

## Installation

### Build from source

```bash
cd tools/rust/git-guard
cargo build --release
```

### Install as PATH override

Create a directory that appears before `/usr/bin` in your PATH:

```bash
mkdir -p ~/.local/bin
cp target/release/git ~/.local/bin/git
```

Ensure `~/.local/bin` is first in your PATH (add to `.bashrc` or `.zshrc`):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Verify installation

```bash
# Should show git-guard blocking the operation
git push --force

# Should execute real git
git status
```

## How It Works

1. Intercepts all `git` commands
2. Checks arguments for dangerous flags or protected branch targets
3. If dangerous operation detected:
   - Prints a clear error message
   - Exits with code 1
4. Otherwise, executes the real `git` binary transparently

## Example Output

```
============================================================
GIT-GUARD: OPERATION BLOCKED
============================================================

The following operation(s) are not allowed:

  - push to main : Direct push to protected branch bypasses PR review

This safety mechanism prevents AI assistants from performing
destructive git operations or bypassing code review.

If you absolutely need to perform this operation, use the
real git binary directly:

  /usr/bin/git <your command>

============================================================
```

## Emergency Bypass

If you absolutely need to perform a blocked operation (e.g., emergency hotfix), use the real git binary directly:

```bash
/usr/bin/git push --force origin main
```

## Running Tests

```bash
cargo test
```

## Security Considerations

- The wrapper finds the real `git` binary by searching PATH, skipping itself
- The wrapper uses `exec()` on Unix to replace itself with the real git process
- All safe operations pass through without modification
- Blocked operations can be bypassed by calling `/usr/bin/git` directly (intentional escape hatch)

## License

MIT
