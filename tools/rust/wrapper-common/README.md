# wrapper-common

> Shared Rust library for CLI wrapper hardening. Provides binary discovery, structured audit logging, compile-time integrity verification, and platform-specific process execution for git-guard and gh-validator.

## Overview

This library contains the common functionality used by the wrapper-guard binaries (`git-guard` and `gh-validator`). These wrappers intercept `git` and `gh` commands to enforce security policies, log all invocations, and prevent dangerous operations.

Key capabilities:

- **Binary finder** -- locates the real binary while avoiding infinite recursion between wrapper copies
- **Audit logging** -- structured JSON logs of every command invocation with caller identification
- **Integrity verification** -- compile-time SHA-256 source hashing for tamper detection
- **Process execution** -- Unix `exec()` replacement or Windows `spawn()` with inherited I/O

## Modules

### `binary_finder`

Finds the real binary (e.g., the actual `git` or `gh`) using a priority chain:

1. **Hardened path** (`/usr/lib/wrapper-guard/{name}.real`) -- checked first, used by setgid wrappers
2. **Recursion guard** -- binary-specific env var (`__WRAPPER_GUARD_RECURSION_GIT`) detects exec loops between multiple wrapper copies
3. **PATH scanning** -- searches PATH, skipping self and same-sized non-setgid copies (likely other wrapper binaries)

Results are cached after first resolution.

### `audit`

Structured JSON audit logging with:

- ISO 8601 timestamps
- Caller PID, parent PID, UID, and parent executable path (Linux)
- Sanitized arguments (secrets masked by callers)
- Action classification: `allowed`, `blocked`, `error`
- Blocked reason tracking
- Best-effort writes with size-based rotation at 10 MB
- Configurable log directory via `WRAPPER_GUARD_LOG_DIR` env var

Default log location: `~/.local/share/wrapper-guard/audit.log`

### `integrity`

Compile-time integrity verification:

- Wrappers embed a SHA-256 hash of their source files via `build.rs`
- The `--wrapper-integrity` flag prints the wrapper name, source hash, and binary path
- Hash validation utilities for external verification scripts

### `exec`

Platform-specific binary execution:

- **Unix**: `exec()` replaces the current process entirely (no return on success)
- **Windows**: `spawn()` with exit code forwarding
- **`spawn_binary()`**: non-replacing child process for post-command work (e.g., audit logging after completion)

### `error`

Fail-closed error types with helpful diagnostics:

- `BinaryNotFound` -- with searched paths and recursion detection details
- `ExecFailed` -- wraps `io::Error` from exec/spawn
- `IntegrityFailure` -- tamper detection
- `AuditLogError` -- non-fatal logging failures

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `WRAPPER_GUARD_LOG_DIR` | `~/.local/share/wrapper-guard/` | Audit log directory |

## Usage

This is a library crate, not a standalone binary. Add it as a dependency:

```toml
[dependencies]
wrapper-common = { path = "../wrapper-common" }
```

Example usage in a wrapper binary:

```rust
use wrapper_common::binary_finder::{find_real_binary, set_recursion_guard};
use wrapper_common::audit::{AuditEntry, AuditAction, log_event};
use wrapper_common::integrity::check_integrity_flag;
use wrapper_common::exec::exec_binary;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    // Handle --wrapper-integrity flag
    if check_integrity_flag(&args, "git-guard", SOURCE_HASH) {
        std::process::exit(0);
    }

    // Find the real binary
    let real_path = find_real_binary("git").expect("git not found");

    // Log the invocation
    let entry = AuditEntry::new("git-guard", AuditAction::Allowed, args.clone(), &real_path.to_string_lossy(), SOURCE_HASH);
    log_event(&entry);

    // Set recursion guard and exec
    set_recursion_guard("git");
    exec_binary("git", &real_path, &args).expect("exec failed");
}
```

## Wrapper Chain Architecture

The two-wrapper chain for hardened installations:

```
~/.local/bin/git (non-setgid wrapper)
  -> sets __WRAPPER_GUARD_RECURSION_GIT
  -> exec /usr/bin/git (setgid wrapper, wrapper-guard group)
     -> finds /usr/lib/wrapper-guard/git.real (accessible via group)
     -> exec git.real
```

The recursion guard is binary-specific (`_GIT` vs `_GH`) so that `gh` calling `git` internally does not trigger false recursion detection.

## Project Structure

```
tools/rust/wrapper-common/
├── Cargo.toml          # Package configuration
├── README.md           # This file
└── src/
    ├── lib.rs          # Module declarations
    ├── binary_finder.rs # Real binary discovery with caching
    ├── audit.rs        # Structured JSON audit logging
    ├── integrity.rs    # Compile-time source hash verification
    ├── exec.rs         # Platform-specific process execution
    └── error.rs        # Error types with fail-closed semantics
```

## Dependencies

- [sha2](https://docs.rs/sha2) - SHA-256 for integrity verification
- [chrono](https://docs.rs/chrono) - ISO 8601 timestamps for audit entries
- [serde](https://docs.rs/serde) / [serde_json](https://docs.rs/serde_json) - JSON audit log serialization
- [once_cell](https://docs.rs/once_cell) - Lazy binary path cache

## License

Part of the template-repo project. See repository LICENSE file.
