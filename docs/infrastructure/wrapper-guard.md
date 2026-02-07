# Wrapper Guard: CLI Binary Hardening

## Overview

Wrapper Guard is a defense-in-depth security system that prevents AI agents (and other automated tools) from bypassing CLI wrapper protections. It hardens the `git-guard` and `gh-validator` wrappers so that the real `git` and `gh` binaries cannot be directly invoked, even by a determined adversary.

The system consists of five layers:

1. **Shared hardening library** (`wrapper-common`) with common security primitives
2. **Structured audit logging** for forensic analysis of all wrapper invocations
3. **Compile-time integrity hashing** for tamper detection and version verification
4. **Binary relocation with group-restricted permissions** (host systems)
5. **Hardened container image** with no bypass paths (CI/automated agents)

## Threat Model

### What we protect against

The wrappers (`git-guard`, `gh-validator`) shadow system binaries by being installed earlier in `$PATH`. Without hardening, an adversary can trivially bypass them:

| Bypass Method | Pre-Hardening | Post-Hardening |
|--------------|:---:|:---:|
| Call `/usr/bin/git` directly | Works | Permission denied |
| Manipulate `$PATH` ordering | Works | Real binary still restricted |
| Install a second `git` binary | Works | Container removes `apt`/`curl`/`wget` |
| Symlink/copy real binary | Works | Source is permission-restricted |
| Use `env -i git` to clear PATH | Works | Wrapper is at `/usr/bin/git` |
| Read real binary bytes and re-create | Works | Source requires group membership to read |

### Who is the adversary?

Primarily AI coding agents running in automated environments. These agents:
- Execute shell commands and can inspect the filesystem
- May attempt to force-push, skip hooks, or post unmasked secrets
- Run as unprivileged users (not root, not in the `wrapper-guard` group)

Human administrators retain emergency bypass access through group membership.

## Architecture

```
                    User/Agent runs "git push --force"
                              |
                              v
                    /usr/bin/git (wrapper)
                              |
                    +--- git-guard logic ---+
                    |  1. Check --wrapper-integrity flag
                    |  2. Find real binary (hardened path first)
                    |  3. Detect dangerous operations
                    |  4. Log audit entry (JSON)
                    |  5. Block or exec real binary
                    +------------------------+
                              |
              +---------------+--------------+
              |                              |
         [BLOCKED]                     [ALLOWED]
         - Log to audit.log           - Log to audit.log
         - Print error to stderr      - exec() real binary
         - Exit 1                     - Process replaced
```

### Component Layout

| Component | Path | Purpose |
|-----------|------|---------|
| `wrapper-common` | `tools/rust/wrapper-common/` | Shared library crate |
| `git-guard` | `tools/rust/git-guard/` | Git wrapper (blocks force-push, no-verify, push to main) |
| `gh-validator` | `tools/rust/gh-validator/` | GitHub CLI wrapper (masks secrets, validates URLs) |
| Setup script | `automation/setup/security/setup-wrapper-guard.sh` | Host hardening (requires sudo) |
| Uninstall script | `automation/setup/security/uninstall-wrapper-guard.sh` | Reverses setup |
| Verify script | `automation/setup/security/verify-wrapper-guard.sh` | Checks integrity |
| Container | `docker/hardened-agent.Dockerfile` | Hardened Docker image |

## Layer 1: Shared Library (`wrapper-common`)

Both wrappers depend on `wrapper-common`, which provides:

### Binary Discovery (`binary_finder`)

Finds the real binary while avoiding infinite recursion (calling itself):

1. **Hardened path** -- checks `/usr/lib/wrapper-guard/{name}.real` first
2. **PATH scan fallback** -- iterates `$PATH`, canonicalizes each candidate, skips self
3. **Caching** -- resolved paths are cached in a `Mutex<HashMap>` for subsequent calls

This design means the same compiled wrapper works in both hardened and non-hardened environments. If the setup script hasn't been run, it falls back to PATH scanning (the pre-hardening behavior).

### Process Execution (`exec`)

Platform-specific execution:
- **Unix**: Uses `exec()` syscall to replace the wrapper process entirely. The real binary inherits the wrapper's PID, file descriptors, and signal handlers.
- **Windows**: Spawns the real binary and exits with the child's exit code.

### Error Handling (`error`)

A unified `CommonError` enum with `help_text()` methods that provide actionable guidance. Both wrappers wrap this with `#[from]` derive for transparent error propagation.

## Layer 2: Audit Logging

Every wrapper invocation produces a structured JSON log entry, regardless of whether the operation is allowed or blocked.

### Log Format (JSONL)

Each line in the log file is a complete JSON object:

```json
{
  "timestamp": "2025-01-15T10:30:45.123456Z",
  "wrapper": "git-guard",
  "action": "blocked",
  "args_sanitized": ["push", "--force", "origin", "main"],
  "blocked_reason": "--force: Force push can overwrite remote history",
  "caller_pid": 12345,
  "caller_ppid": 12300,
  "caller_exe": "/usr/bin/python3",
  "caller_uid": 1000,
  "real_binary_path": "/usr/lib/wrapper-guard/git.real",
  "source_hash": "a1b2c3d4e5f6..."
}
```

### Fields

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 UTC timestamp |
| `wrapper` | Which wrapper generated this entry (`git-guard` or `gh-validator`) |
| `action` | `allowed`, `blocked`, or `error` |
| `args_sanitized` | Command arguments (secrets already masked by gh-validator) |
| `blocked_reason` | Why the operation was blocked (absent for allowed operations) |
| `caller_pid` | PID of the wrapper process |
| `caller_ppid` | Parent PID (the process that invoked the wrapper) |
| `caller_exe` | Executable path of the parent process (Linux only, via `/proc/<ppid>/exe`) |
| `caller_uid` | UID of the calling user (read from `/proc/self/status`) |
| `real_binary_path` | Path to the real binary being invoked |
| `source_hash` | Compile-time SHA-256 hash identifying the wrapper version |

### Configuration

| Setting | Default | Override |
|---------|---------|----------|
| Log directory | `$HOME/.local/share/wrapper-guard/` | `WRAPPER_GUARD_LOG_DIR` env var |
| Log file | `audit.log` | N/A |
| Max file size | 10 MB | N/A |
| Rotation | Rename to `.log.1` on threshold | N/A |

### Design Principles

- **Best-effort**: Log failures are printed to stderr but never block the wrapper from executing. The wrapper's primary function (blocking dangerous operations) always takes priority.
- **No libc dependency**: UID is read from `/proc/self/status` rather than calling `getuid()`. This avoids pulling in the `libc` crate.
- **Caller identification**: On Linux, `readlink(/proc/<ppid>/exe)` identifies exactly which program called the wrapper. This is useful for distinguishing between a human terminal session (`/bin/bash`) and an AI agent (`/usr/bin/python3`).

## Layer 3: Compile-Time Integrity Hashing

Each wrapper embeds a SHA-256 hash of its source files, computed at compile time by `build.rs`.

### How it works

1. `build.rs` walks all `src/**/*.rs` files and `Cargo.toml` in sorted order
2. Computes SHA-256 of the concatenated contents
3. Writes `const SOURCE_HASH: &str = "<64-char hex>";` to `$OUT_DIR/integrity.rs`
4. The wrapper includes this with `include!(concat!(env!("OUT_DIR"), "/integrity.rs"))`
5. `cargo:rerun-if-changed=src/` ensures the hash updates on any source change

### The `--wrapper-integrity` flag

Both wrappers respond to a special flag:

```bash
git --wrapper-integrity
# Output: git-guard source_hash=a1b2c3d4e5f6...

gh --wrapper-integrity
# Output: gh-validator source_hash=f6e5d4c3b2a1...
```

This is checked before any other logic runs (before binary discovery, before argument parsing). It enables:

- **Verification scripts** to confirm the installed wrapper matches expectations
- **Audit logs** to include the source hash for version tracking
- **Integrity file** (`/usr/lib/wrapper-guard/integrity.json`) to record hashes at setup time

### What it does NOT do

The source hash is not a runtime tamper-detection mechanism. A modified binary could simply return a fake hash. Its purpose is **version identification** and **known-good baseline comparison** -- the setup script records the hash at install time, and the verify script compares against that baseline.

## Layer 4: Binary Relocation (Host Systems)

The `setup-wrapper-guard.sh` script hardens a Debian/Ubuntu host by physically relocating the real binaries to a permission-restricted directory.

### Prerequisites

- Debian or Ubuntu (requires `dpkg-divert`)
- `sudo` access
- Wrapper binaries already built and installed (via `tools/rust/install-all.sh`)

### What the setup script does

```
Step 1: Create system group "wrapper-guard"
         groupadd --system wrapper-guard

Step 2: Create restricted directory
         /usr/lib/wrapper-guard/  (root:wrapper-guard 0750)

Step 3: Relocate real binaries with dpkg-divert
         /usr/bin/git  -->  /usr/lib/wrapper-guard/git.real  (root:wrapper-guard 0750)
         /usr/bin/gh   -->  /usr/lib/wrapper-guard/gh.real   (root:wrapper-guard 0750)

Step 4: Install wrapper binaries in place of originals (setgid wrapper-guard)
         git-guard  -->  /usr/bin/git   (root:wrapper-guard 2755)
         gh-validator  -->  /usr/bin/gh (root:wrapper-guard 2755)

Step 5: Record integrity hashes to /usr/lib/wrapper-guard/integrity.json
```

### Why `dpkg-divert`?

`dpkg-divert` is the Debian package manager's mechanism for telling `apt` that a file has been intentionally moved. When the `git` or `gh` package is updated:
- Without `dpkg-divert`: `apt upgrade` would overwrite the wrapper at `/usr/bin/git` with the new real binary, undoing our setup.
- With `dpkg-divert`: `apt upgrade` places the new binary at `/usr/lib/wrapper-guard/git.real`, preserving the wrapper at `/usr/bin/git`.

### Permission model

```
/usr/lib/wrapper-guard/           root:wrapper-guard  0750  (drwxr-x---)
/usr/lib/wrapper-guard/git.real   root:wrapper-guard  0750  (-rwxr-x---)
/usr/lib/wrapper-guard/gh.real    root:wrapper-guard  0750  (-rwxr-x---)
/usr/bin/git                      root:wrapper-guard  2755  (-rwxr-sr-x)  [wrapper, setgid]
/usr/bin/gh                       root:wrapper-guard  2755  (-rwxr-sr-x)  [wrapper, setgid]
```

- **Any user** can execute `/usr/bin/git` (the wrapper). The wrapper enforces policy.
- Wrappers are **setgid `wrapper-guard`**, so the wrapper process inherits group permission to execute the real binaries without granting the agent user direct access.
- **Only `root`** can execute the real binaries directly (no users are added to the group by default).
- AI agents cannot read, execute, or copy the real binaries.
- Human administrators can bypass via `sudo`.

### Emergency bypass

After setup, administrators who need to bypass the wrapper (e.g., for a legitimate force-push) must use `sudo`:

```bash
sudo /usr/lib/wrapper-guard/git.real push --force origin main
```

No users are added to the `wrapper-guard` group by default. The setgid bit on the wrappers is what allows them to execute the real binaries. To grant a user direct bypass access without sudo (not recommended):

```bash
sudo usermod -aG wrapper-guard <username>
# Log out and back in for group membership to take effect
```

### Uninstalling

```bash
sudo bash automation/setup/security/uninstall-wrapper-guard.sh
```

This reverses the `dpkg-divert`, restores the original binaries to `/usr/bin/`, and removes the restricted directory. Pass `--remove-group` to also delete the system group.

### Verification

```bash
sudo bash automation/setup/security/verify-wrapper-guard.sh
```

Checks:
1. `wrapper-guard` group exists
2. `/usr/lib/wrapper-guard/` permissions are correct
3. Real binary permissions are correct
4. Wrapper integrity hashes match the recorded baseline
5. `dpkg-divert` entries are in place
6. Binary SHA-256 checksums match

## Layer 5: Hardened Container (CI/Automated Agents)

For CI pipelines and automated agent environments, a Docker container provides the strongest isolation.

### Container design

The `docker/hardened-agent.Dockerfile` uses multi-stage builds:

**Build stage**: Compiles `wrapper-common`, `git-guard`, and `gh-validator` from source.

**Runtime stage**:
1. Installs real `git` and `gh` binaries
2. Moves them to `/usr/lib/wrapper-guard/` with `root:wrapper-guard 0750` permissions
3. Installs wrapper binaries as `/usr/bin/git` and `/usr/bin/gh`
4. **Removes all bypass tools**: `apt`, `dpkg`, `curl`, `wget`, `gpg`
5. Creates a non-root `agent` user **not** in the `wrapper-guard` group
6. Verifies the setup at build time with `--wrapper-integrity`

### What the agent cannot do

| Attempted Action | Result |
|-----------------|--------|
| `/usr/lib/wrapper-guard/git.real --version` | Permission denied (not in group) |
| `apt install git` | Command not found (apt removed) |
| `curl -o /tmp/git https://...` | Command not found (curl removed) |
| `wget https://...` | Command not found (wget removed) |
| `cp /usr/lib/wrapper-guard/git.real /tmp/` | Permission denied (not in group) |
| `cat /usr/lib/wrapper-guard/git.real > /tmp/git` | Permission denied (not in group) |
| `PATH=/usr/lib/wrapper-guard:$PATH git` | Permission denied (not in group) |
| Compile a new git from source | No compiler, no package manager |

### Usage

```bash
# Build the container
docker compose --profile hardened build hardened-agent

# Run a command through the wrapper
docker compose --profile hardened run --rm hardened-agent git status

# Verify force-push is blocked
docker compose --profile hardened run --rm hardened-agent git push --force  # BLOCKED

# Verify direct access is denied
docker compose --profile hardened run --rm hardened-agent \
  /usr/lib/wrapper-guard/git.real --version  # Permission denied

# Interactive shell for inspection
docker compose --profile hardened run --rm hardened-agent bash
```

The container runs with a read-only root filesystem and tmpfs for `/tmp` (configured in `docker-compose.yml`).

## CI Integration

The CI pipeline validates all wrapper code with four stages:

```bash
# Format check
automation-cli ci run wrapper-fmt

# Lint check (clippy -D warnings)
automation-cli ci run wrapper-clippy

# Unit tests
automation-cli ci run wrapper-test

# All three above in sequence
automation-cli ci run wrapper-full
```

These stages check `wrapper-common`, `git-guard`, and `gh-validator` together.

## Quick Reference

### Installation (non-hardened, PATH-based)

```bash
# Build and install all wrappers to ~/.local/bin
./tools/rust/install-all.sh

# Ensure ~/.local/bin is before /usr/bin in PATH
export PATH="$HOME/.local/bin:$PATH"
```

### Installation (hardened, host system)

```bash
# Build wrappers first
./tools/rust/install-all.sh

# Run the hardening setup (requires sudo)
sudo bash automation/setup/security/setup-wrapper-guard.sh

# Log out and back in for group membership
# Verify the installation
sudo bash automation/setup/security/verify-wrapper-guard.sh
```

### Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `WRAPPER_GUARD_LOG_DIR` | Override audit log directory | `$HOME/.local/share/wrapper-guard/` |

### Key file locations

| File | Purpose |
|------|---------|
| `~/.local/share/wrapper-guard/audit.log` | Audit log (JSONL) |
| `/usr/lib/wrapper-guard/integrity.json` | Recorded hashes from setup |
| `/usr/lib/wrapper-guard/git.real` | Real git binary (hardened mode) |
| `/usr/lib/wrapper-guard/gh.real` | Real gh binary (hardened mode) |

## Limitations and Known Gaps

1. **Root can bypass everything**. If an agent has root access, no filesystem-based restriction will hold. The container layer mitigates this by not granting root to the agent user.

2. **Kernel-level bypass**. An adversary with kernel module loading capability or `ptrace` access could bypass file permissions. This is outside scope.

3. **Non-Debian systems**. The `setup-wrapper-guard.sh` script uses `dpkg-divert`, which is Debian/Ubuntu-specific. On other distributions, manual binary relocation is needed.

4. **Source hash is not runtime tamper detection**. A modified binary can return any hash. The hash is useful for version identification and baseline comparison, not for proving the binary hasn't been modified at rest.

5. **Audit logging is best-effort**. If the log directory is not writable, the wrapper still executes the command. This is intentional -- the wrapper's primary function (policy enforcement) should never be blocked by a logging failure.

## Related Documentation

- [AI Agents Security](../agents/security.md) -- Overall agent security model
- [AI Agents Security (Detailed)](../agents/security-detailed.md) -- Deep dive into agent security
- [Containerization](containerization.md) -- Container-first philosophy
- [Git Hooks](git-hooks.md) -- Pre-commit and pre-push hooks
