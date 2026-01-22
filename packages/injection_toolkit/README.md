# Injection Toolkit

[![PR Validation](https://github.com/AndrewAltimit/template-repo/actions/workflows/pr-validation.yml/badge.svg)](https://github.com/AndrewAltimit/template-repo/actions/workflows/pr-validation.yml)

A cross-platform framework for runtime integration with closed-source applications.

## Overview

The Injection Toolkit provides reusable components for:
- Injecting minimal code into target applications
- Extracting runtime state via IPC
- Rendering overlays on top of applications
- Synchronizing state across multiple clients

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Systems                          │
│              (MCP Server, AI Agents, Other Clients)              │
└──────────────────────────────┬──────────────────────────────────┘
                               │ IPC (queries/responses)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                           Daemon                                 │
│                                                                  │
│  • Aggregates state from injector                               │
│  • Serves queries from clients                                  │
│  • Optional: multiplayer synchronization                        │
└───────────────────────────────┬──────────────────────────────────┘
                                │ IPC (state updates)
           ┌────────────────────┼────────────────────┐
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────┐  ┌─────────────────┐  ┌────────────────────┐
│    Injector      │  │  Shared Memory  │  │      Overlay       │
│                  │  │                 │  │                    │
│  • Minimal code  │  │  • Frame data   │  │  • Renders content │
│  • State export  │  │  • Lock-free    │  │  • Click-through   │
│  • Hooks         │  │  • Triple-buf   │  │  • Interactive UI  │
└────────┬─────────┘  └─────────────────┘  └────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Target Application                          │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Core Libraries

| Crate | Description |
|-------|-------------|
| `itk-protocol` | Wire protocol with versioning and CRC validation |
| `itk-shmem` | Cross-platform shared memory (Windows/Linux) |
| `itk-ipc` | Cross-platform IPC channels (named pipes/Unix sockets) |
| `itk-sync` | Clock synchronization and drift correction |

### Templates

| Template | Platform | Description |
|----------|----------|-------------|
| `itk-daemon` | All | Central coordinator daemon |
| `itk-overlay` | All | wgpu-based transparent overlay window |
| `itk-native-dll` | Windows | DLL injection template |
| `itk-ld-preload` | Linux | LD_PRELOAD injection template |

## Quick Start

### 1. Create a New Project

```bash
# Copy a project template
cp -r packages/injection_toolkit/projects/template packages/injection_toolkit/projects/my-project
```

### 2. Customize the Injector

Edit the injector to extract the state you need:

```rust
// Windows DLL example
fn on_attach() {
    // Connect to daemon
    let channel = itk_ipc::connect("my_app_injector")?;

    // Set up hooks to intercept relevant functions
    // ...

    // Send state updates
    send_state_event("player_position", r#"{"x": 100, "y": 200}"#);
}
```

### 3. Configure the Daemon

```rust
let config = DaemonConfig {
    app_id: "my_app".to_string(),
    injector_channel: "my_app_injector".to_string(),
    client_channel: "my_app_client".to_string(),
    enable_sync: false,
};

let daemon = Daemon::new(config);
daemon.run()?;
```

### 4. Run the Overlay (Optional)

```bash
cargo run --release -p itk-overlay
```

## Platform Support

| Platform | Injection | IPC | Shared Memory | Overlay |
|----------|-----------|-----|---------------|---------|
| Windows | Native DLL, Reloaded-II, MelonLoader | Named Pipes | CreateFileMapping | WS_EX_TRANSPARENT |
| Linux | LD_PRELOAD, ptrace | Unix Sockets | shm_open | X11 SHAPE extension |
| Linux (Wayland) | LD_PRELOAD | Unix Sockets | shm_open | Limited* |

*Wayland overlay support requires layer-shell protocol and compositor support.

## Design Principles

### 1. Minimal Injection

Keep injected code as small as possible:
- Reduces crash risk in target application
- Smaller reverse-engineering surface
- Easier to update when target changes

### 2. Update Resilience

Design for target application updates:
- Use signature scanning with graceful fallback
- Version-gate features
- Log detailed errors for debugging

### 3. Process Isolation

Keep components separate:
- Daemon crash doesn't affect target
- Target crash doesn't lose state
- Components can be restarted independently

### 4. Lock-Free Communication

Use lock-free data structures where possible:
- Seqlock for shared memory
- Non-blocking IPC patterns
- Avoid priority inversion

## Building

### Prerequisites

- Rust 1.70+
- Platform-specific dependencies (see below)

### Linux

```bash
# Install X11 development libraries
sudo apt install libx11-dev libxext-dev

# Build all components
cargo build --release -p itk-daemon -p itk-overlay -p itk-ld-preload
```

### Windows

```bash
# Build all components
cargo build --release -p itk-daemon -p itk-overlay -p itk-native-dll
```

### Cross-Compilation

```bash
# Linux to Windows
cargo build --release --target x86_64-pc-windows-gnu -p itk-native-dll

# Windows to Linux (requires cross or similar)
cross build --release --target x86_64-unknown-linux-gnu -p itk-ld-preload
```

## Testing

```bash
# Run unit tests
cargo test -p itk-protocol -p itk-shmem -p itk-ipc

# Run Loom concurrency tests (verifies seqlock memory ordering)
RUSTFLAGS="--cfg loom" cargo test -p itk-shmem loom_tests

# Run Miri for undefined behavior detection
cargo +nightly miri test -p itk-shmem -- seqlock

# Cross-compilation check (verify code compiles for other targets)
cargo check --target x86_64-unknown-linux-gnu -p itk-ipc -p itk-shmem
cargo check --target x86_64-pc-windows-gnu -p itk-ipc -p itk-shmem
```

### CI Pipeline

The injection toolkit tests run automatically as part of PR validation when files in `packages/injection_toolkit` are changed:

| Stage | Tool | Purpose |
|-------|------|---------|
| Lint | clippy, rustfmt | Code quality and formatting |
| Unit Tests | cargo test | Core functionality |
| Loom | loom crate | Explores all thread interleavings |
| Miri | miri | Detects undefined behavior |
| Cross-Compile | cargo check | Verifies Windows/x86 compilation |

Tests run on the ARM64 self-hosted runner, with cross-compilation verification for x86_64 Linux and Windows targets.

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component design, data flow, security model |
| [MIGRATION.md](docs/MIGRATION.md) | FlatBuffers migration plan and compatibility |

## Security Considerations

- **Threat model**: Injector data is treated as untrusted (see [Security](docs/ARCHITECTURE.md#security))
- Injected code runs with target application privileges
- IPC channels use same-user access controls by default
- Input validation protects against malformed data
- No network exposure for local IPC
- Consider code signing for distributed DLLs

## License

Part of the template-repo project. See repository LICENSE file.
