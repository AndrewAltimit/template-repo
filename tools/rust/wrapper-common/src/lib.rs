//! Shared library for CLI wrapper hardening.
//!
//! Provides the pieces git-guard and gh-validator have in common:
//! - [`binary_finder`]: locate the real binary (hardened path, then PATH)
//!   without recursing into the wrapper itself or another wrapper copy
//! - [`exec`]: replace the process (Unix) or run-and-forward-exit-code,
//!   with correct signal / Ctrl-C and exit-status passthrough
//! - [`audit`]: best-effort JSONL audit log with credential redaction
//! - [`integrity`]: compile-time source hash and `--wrapper-integrity`
//! - [`platform`]: small OS queries (uid, setgid detection) without libc
//!
//! The crate deliberately has a single runtime dependency (`thiserror`) so
//! the wrappers, which run on every `git` / `gh` invocation, start fast.

pub mod audit;
pub mod binary_finder;
pub mod error;
pub mod exec;
pub mod integrity;
pub mod platform;

#[cfg(feature = "build")]
pub mod source_hash;

/// Build-script entry point for the wrappers.
///
/// Hashes the calling crate's `src/**/*.rs` and `Cargo.toml` together with
/// [`integrity::COMMON_SOURCE_HASH`] and writes
/// `const SOURCE_HASH: &str = "...";` to `$OUT_DIR/integrity.rs`.
#[cfg(feature = "build")]
pub fn emit_wrapper_source_hash() {
    println!("cargo:rerun-if-changed=src");
    println!("cargo:rerun-if-changed=Cargo.toml");
    let crate_dir = std::path::PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR not set"),
    );
    let hash = source_hash::hash_crate(&crate_dir, &[integrity::COMMON_SOURCE_HASH]);
    source_hash::write_const("integrity.rs", "SOURCE_HASH", &hash);
}
