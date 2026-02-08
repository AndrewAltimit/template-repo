# rust-psp (vendored fork)

> Rust SDK for Sony PSP homebrew development -- modernized fork with edition 2024, safety fixes, and kernel mode support.

**Upstream:** [github.com/overdrivenpotato/rust-psp](https://github.com/overdrivenpotato/rust-psp) (MIT license)

This is a vendored fork maintained as part of the [OASIS_OS](../oasis_os/) project. The upstream project is maintained at a low cadence and lacks kernel mode support. This fork diverges for edition 2024 compatibility, safety hardening, and feature additions while tracking upstream for bug fixes.

```rust
#![no_std]
#![no_main]

psp::module!("sample_module", 1, 1);

fn psp_main() {
    psp::enable_home_button();
    psp::dprintln!("Hello PSP from rust!");
}
```

See `examples/` directory for sample programs.

## Modifications from Upstream

### Edition 2024 and Toolchain

- Workspace and all crates updated to Rust edition 2024
- All `#[no_mangle]` and `#[link_section]` attributes updated to `#[unsafe(no_mangle)]` / `#[unsafe(link_section)]` syntax
- Re-exported `paste::paste` for `$crate::paste!` macro resolution in edition 2024
- Workspace lints configured (`unsafe_op_in_unsafe_fn = "warn"`, clippy lints)

### Safety Fixes

- **C runtime intrinsics (CRITICAL):** Reverted `memset`/`memcpy`/`memmove` implementations to manual byte loops. LLVM lowers `core::ptr::write_bytes`/`copy`/`copy_nonoverlapping` back to C memset/memcpy/memmove calls, causing infinite recursion when those functions ARE the implementation. On MIPS this manifests as "jump to invalid address", not a stack overflow.
- **Use-after-free in test_runner:** Fixed `psp_filename()` returning a pointer to a dropped `String` -- the format buffer now outlives the syscall.
- **Thread-unsafe panic counter:** Replaced `static mut PANIC_COUNT` with `AtomicUsize` for safe concurrent access.
- **Allocator overflow checks:** Added `checked_add` for size + alignment calculations in `SystemAlloc::alloc` to prevent integer overflow.
- **OOM diagnostic:** Added explicit "out of memory" message before spin loop in the allocation error handler.
- **Global allow scoping:** Removed blanket `#![allow(unsafe_op_in_unsafe_fn)]` from crate root; scoped allows only where needed in `debug.rs`, `sys/mod.rs`, `panic.rs`.

### VRAM Allocator

- Changed `alloc()` from panicking to returning `Result<VramMemChunk, VramAllocError>`
- Added structured error types: `OutOfMemory { requested, available }` and `UnsupportedPixelFormat`
- VRAM base address now uses `sceGeEdramGetAddr()` instead of hardcoded constants

### Hardware Constants

- Extracted magic numbers into `psp/src/constants.rs`: `SCREEN_WIDTH`, `SCREEN_HEIGHT`, `BUF_WIDTH`, `VRAM_BASE_UNCACHED`, thread priorities, NID values
- Module macros and `enable_home_button()` use named constants instead of raw numbers

### Error Handling (cargo-psp)

- All tool binaries (`prxgen`, `pack-pbp`, `mksfo`, `cargo-psp`) refactored from `unwrap()`/`panic!()` to `Result` with `anyhow` context
- Descriptive error messages with recovery hints

### Features

- `kernel` feature flag added for kernel mode module support (`PSP_MODULE_INFO` flag `0x1000`)
- `libm` dependency added for floating-point math in `no_std`

## Structure

```
rust_psp_sdk/
+-- psp/                # Core PSP crate (sceGu, sceCtrl, sys bindings, vram_alloc)
+-- cargo-psp/          # Build tool: cross-compile + prxgen + pack-pbp -> EBOOT.PBP
+-- examples/           # Sample programs (hello-world, cube, gu-background, etc.)
+-- ci/                 # CI test harness and std verification
```

## Dependencies

Rust **nightly** toolchain with the `rust-src` component:

```sh
rustup default nightly && rustup component add rust-src
```

The `cargo-psp` build tool is included in this package. Build it from source:

```sh
cd cargo-psp && cargo build --release
# Binary at: target/release/cargo-psp
```

Or use it directly via `cargo run`:

```sh
cd /path/to/your/psp/project
cargo +nightly psp --release
```

**Do NOT run `cargo install cargo-psp`** -- this would install the upstream version from crates.io, not this fork. Use the local `cargo-psp/` directory.

## Running Examples

Enter one of the example directories, `examples/hello-world` for instance, and
run `cargo psp`.

This will create an `EBOOT.PBP` file under `target/mipsel-sony-psp/debug/`

Assuming you have a PSP with custom firmware installed, you can simply copy this
file into a new directory under `PSP/GAME` on your memory stick, and it will
show up in your XMB menu.

```
.
+-- PSP
    +-- GAME
        +-- hello-world
            +-- EBOOT.PBP
```

If you do not have a PSP, we recommend using the [PPSSPP emulator](http://ppsspp.org).
Note that graphics code is very sensitive so if you're writing graphics code we
recommend developing on real hardware. PPSSPP is more relaxed in some aspects.

## Usage

To use the `psp` crate from another crate in this monorepo, add it as a path
dependency:

```toml
[dependencies]
psp = { path = "../../../rust_psp_sdk/psp" }
```

In your `main.rs` file, set up a basic skeleton:

```rust
#![no_std]
#![no_main]

psp::module!("sample_module", 1, 0);

fn psp_main() {
    psp::enable_home_button();
    psp::dprintln!("Hello PSP from rust!");
}
```

Run `cargo +nightly psp` to build your `EBOOT.PBP` file, or
`cargo +nightly psp --release` for a release build.

Customize your EBOOT with a `Psp.toml` in your project root (all keys optional):

```toml
title = "XMB title"
xmb_icon_png = "path/to/24bit_144x80_image.png"
xmb_background_png = "path/to/24bit_480x272_background.png"
xmb_music_at3 = "path/to/ATRAC3_audio.at3"
```

More options can be found in the schema definition [here](cargo-psp/src/main.rs#L18-L100).

## Debugging

Using psplink and psp-gdb from the [pspdev github organization](https://github.com/pspdev) (`psplinkusb v3.1.0 and GNU gdb (GDB) 11.0.50.20210718-git` or later), Rust types are fully supported. Enable debug symbols in your release binaries:

```toml
[profile.release]
debug = true
```

Follow the instructions in part 6 of [the PSPlink manual](https://usermanual.wiki/Document/psplinkmanual.1365336729/).

## Troubleshooting

### `error[E0460]: found possibly newer version of crate ...`

```
error[E0460]: found possibly newer version of crate `panic_unwind` which `psp` depends on
```

Clean your target directory:

```sh
cargo clean
```

## Upstream

This project is a completely new SDK with no dependency on the original C/C++
PSPSDK. It aims to be a complete replacement with more efficient implementations
of graphics functions and the addition of missing libraries.

Upstream repository: [github.com/overdrivenpotato/rust-psp](https://github.com/overdrivenpotato/rust-psp)

### Upstream Roadmap

- [x] `core` support
- [x] PSP system library support
- [x] `alloc` support
- [x] `panic = "unwind"` support
- [x] Macro-based VFPU assembler
- [x] Full 3D graphics support
- [x] No dependency on PSPSDK / PSPToolchain
- [x] Full parity with user mode support in PSPSDK
- [x] Port definitions to `libc` crate
- [x] Kernel mode module support (added in this fork via `kernel` feature)
- [ ] Add `std` support
- [ ] Automatically sign EBOOT.PBP files to run on unmodified PSPs
