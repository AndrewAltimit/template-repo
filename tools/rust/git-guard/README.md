# git-guard

A Git CLI wrapper that requires `sudo` for dangerous operations like force push and `--no-verify`.

## Purpose

AI coding assistants (like Claude Code) may sometimes attempt force pushes or skip verification hooks during automated workflows. This wrapper ensures a human must explicitly approve such operations by requiring elevated privileges (sudo).

## Blocked Operations

The following operations require `sudo` to execute:

### Force Push (on `git push` only)
- `--force` / `-f`
- `--force-with-lease`
- `--force-if-includes`

### Skip Hooks
- `--no-verify` (on any command)
- `-n` (only on `commit`, `merge`, `cherry-pick`, `revert` where it means `--no-verify`)

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
2. Checks arguments for dangerous flags
3. If dangerous flags detected AND not running as root/sudo:
   - Prints a clear error message
   - Exits with code 1
4. Otherwise, executes the real `git` binary transparently

## Example Output

```
============================================================
GIT-GUARD: DANGEROUS OPERATION BLOCKED
============================================================

The following dangerous operation(s) require elevated privileges:

  - --force : Force push can overwrite remote history

To proceed, run the command with sudo:

  sudo git <your command>

This safety mechanism prevents AI assistants from performing
destructive git operations without human approval.

============================================================
```

## Running Tests

```bash
cargo test
```

## Security Considerations

- The wrapper finds the real `git` binary by searching PATH, skipping itself
- On Unix, it checks `euid == 0` to detect root privileges
- The wrapper uses `exec()` on Unix to replace itself with the real git process
- All safe operations pass through without modification

## License

MIT
