# OASIS_OS

> An embeddable operating system framework in Rust. Renders a skinnable shell interface -- scene-graph UI, command interpreter, virtual file system, plugin system, remote terminal -- anywhere you can provide a pixel buffer and an input stream.

## Overview

OASIS_OS originated as a Rust port of a PSP homebrew shell OS written in C circa 2006-2008. The trait-based backend system designed for cross-platform portability extends to four targets: PSP hardware (sceGu), desktop/Raspberry Pi (SDL2), Unreal Engine 5 (render target via FFI), and planned framebuffer (headless Pi).

The framework supports multiple "skins" that determine visual layout and feature gating. The Classic skin (implemented) renders a PSIX-style dashboard with document icons, tabbed bars, and chrome bezels. Additional skins (Terminal, Tactical, Corrupted, Desktop, Agent Terminal) are planned.

## Workspace Structure

```
packages/oasis_os/
+-- Cargo.toml                       # Workspace root (resolver="2", edition 2024)
+-- crates/
|   +-- oasis-core/                  # Platform-agnostic framework (SDI, VFS, commands, skins, WM)
|   +-- oasis-backend-sdl/           # SDL2 rendering and input (desktop + Pi)
|   +-- oasis-backend-ue5/           # UE5 software framebuffer + FFI input queue
|   +-- oasis-backend-psp/           # [EXCLUDED] sceGu hardware rendering, PSP controller (no_std)
|   +-- oasis-ffi/                   # C FFI boundary for UE5 integration
|   +-- oasis-app/                   # Binary entry points: desktop app + screenshot tool
+-- skins/
|   +-- classic/                     # PSIX-style icon grid dashboard (implemented)
+-- docs/
    +-- design.md                    # Technical design document (v2.3)
```

The PSP backend is excluded from the workspace (requires `mipsel-sony-psp` target) and depends on the sibling `packages/rust_psp_sdk/` package.

## Build

### Desktop (SDL2)

```bash
# Via Docker (container-first)
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo build --release -p oasis-app

# Or natively
cargo build --release -p oasis-app
```

### PSP (EBOOT.PBP)

Requires the nightly Rust toolchain and `cargo-psp`:

```bash
cd crates/oasis-backend-psp
cargo +nightly psp --release
# Output: target/mipsel-sony-psp/release/EBOOT.PBP
```

### Testing in PPSSPP

The repo includes a containerized PPSSPP emulator with NVIDIA GPU passthrough. Build the image once, then run against any EBOOT:

```bash
# Build the PPSSPP Docker image (first time only)
docker compose --profile psp build ppsspp

# Run with GUI (requires X11 display)
docker compose --profile psp run --rm ppsspp /roms/release/EBOOT.PBP

# Run headless (CI / no display)
docker compose --profile psp run --rm -e PPSSPP_HEADLESS=1 ppsspp /roms/release/EBOOT.PBP --timeout=5

# Run with interpreter (more stable for some MIPS code)
docker compose --profile psp run --rm -e PPSSPP_HEADLESS=1 ppsspp /roms/release/EBOOT.PBP -i --timeout=5
```

The `/roms/` mount maps to `crates/oasis-backend-psp/target/mipsel-sony-psp/` so both `release/` and `debug/` EBOOTs are available.

Headless mode exits with `TIMEOUT` on success (OASIS_OS runs an infinite render loop). Any crash will produce a non-zero exit code.

### UE5 (FFI library)

```bash
cargo build --release -p oasis-ffi
# Output: target/release/liboasis_ffi.so (or .dll on Windows)
```

## CI

```bash
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo fmt --check --all
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo clippy --workspace -- -D warnings
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo test --workspace
```

## Documentation

- [Technical Design Document](docs/design.md) -- architecture, backends, skins, UE5 integration, PSP implementation, development workflow
- Original C source: `psixpsp.7z` at repository root
