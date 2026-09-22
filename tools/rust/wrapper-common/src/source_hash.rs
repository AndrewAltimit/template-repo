//! Deterministic SHA-256 hashing of a crate's sources (build-script helper).
//!
//! This module is compiled in two places:
//! - wrapper-common's own `build.rs` (via `#[path]`) to produce
//!   `COMMON_SOURCE_HASH`, and
//! - the wrappers' build scripts through the `build` feature.
//!
//! It must therefore depend on nothing but `std` and `sha2`.

use sha2::{Digest, Sha256};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

/// Recursively collect `.rs` files under `dir`, sorted for determinism.
pub fn collect_rs_files(dir: &Path) -> Vec<PathBuf> {
    fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
        let Ok(entries) = fs::read_dir(dir) else {
            return;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                walk(&path, out);
            } else if path.extension().is_some_and(|ext| ext == "rs") {
                out.push(path);
            }
        }
    }
    let mut files = Vec::new();
    walk(dir, &mut files);
    files.sort();
    files
}

/// Hash `src/**/*.rs` and `Cargo.toml` of the crate rooted at `crate_dir`,
/// plus any `extra` strings (e.g. the hash of a dependency's sources).
///
/// Paths are hashed relative to `crate_dir` with `/` separators so the result
/// is identical on Unix and Windows.
pub fn hash_crate(crate_dir: &Path, extra: &[&str]) -> String {
    let mut files = collect_rs_files(&crate_dir.join("src"));
    files.push(crate_dir.join("Cargo.toml"));

    let mut hasher = Sha256::new();
    for path in &files {
        let content =
            fs::read(path).unwrap_or_else(|e| panic!("failed to read {}: {e}", path.display()));
        let rel = path.strip_prefix(crate_dir).unwrap_or(path);
        let rel = rel.to_string_lossy().replace('\\', "/");
        hasher.update((rel.len() as u64).to_le_bytes());
        hasher.update(rel.as_bytes());
        hasher.update((content.len() as u64).to_le_bytes());
        hasher.update(&content);
    }
    for value in extra {
        hasher.update(b"extra:");
        hasher.update(value.as_bytes());
    }
    format!("{:x}", hasher.finalize())
}

/// Write `pub const {name}: &str = "{value}";` to `$OUT_DIR/{file_name}`.
pub fn write_const(file_name: &str, name: &str, value: &str) {
    let out_dir = std::env::var_os("OUT_DIR").expect("OUT_DIR not set (not in a build script?)");
    let dest = Path::new(&out_dir).join(file_name);
    let mut file = fs::File::create(&dest)
        .unwrap_or_else(|e| panic!("failed to create {}: {e}", dest.display()));
    writeln!(
        file,
        "/// SHA-256 of the crate sources at compile time.\n\
         #[allow(dead_code)]\n\
         pub const {name}: &str = \"{value}\";"
    )
    .expect("failed to write source hash");
}
