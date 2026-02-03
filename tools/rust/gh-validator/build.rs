//! Build script for gh-validator
//!
//! Computes a SHA-256 hash of all source files and Cargo.toml,
//! embedding it as a compile-time constant for integrity verification.

use sha2::{Digest, Sha256};
use std::fs;
use std::io::Write;
use std::path::Path;

fn main() {
    println!("cargo:rerun-if-changed=src/");
    println!("cargo:rerun-if-changed=Cargo.toml");

    let mut hasher = Sha256::new();

    // Collect and sort all source files for deterministic ordering
    let mut paths = Vec::new();
    collect_rs_files(Path::new("src"), &mut paths);
    paths.sort();

    for path in &paths {
        let content = fs::read(path).unwrap_or_else(|e| {
            panic!("Failed to read {}: {}", path.display(), e);
        });
        // Include the relative path in the hash to detect renames
        hasher.update(path.to_string_lossy().as_bytes());
        hasher.update(&content);
    }

    // Also hash Cargo.toml (dependency changes matter for integrity)
    if let Ok(cargo_toml) = fs::read("Cargo.toml") {
        hasher.update(b"Cargo.toml");
        hasher.update(&cargo_toml);
    }

    let hash = format!("{:x}", hasher.finalize());

    let out_dir = std::env::var("OUT_DIR").expect("OUT_DIR not set");
    let dest = Path::new(&out_dir).join("integrity.rs");
    let mut file = fs::File::create(&dest).expect("Failed to create integrity.rs");
    writeln!(
        file,
        "/// SHA-256 hash of source files at compile time\n\
         #[allow(dead_code)]\n\
         const SOURCE_HASH: &str = \"{}\";",
        hash
    )
    .expect("Failed to write integrity.rs");
}

/// Recursively collect all .rs files under a directory
fn collect_rs_files(dir: &Path, files: &mut Vec<std::path::PathBuf>) {
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                collect_rs_files(&path, files);
            } else if path.extension().is_some_and(|ext| ext == "rs") {
                files.push(path);
            }
        }
    }
}
