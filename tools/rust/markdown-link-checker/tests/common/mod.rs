//! Shared helpers for integration tests.
//!
//! Fixture files are committed with an extra `.in` suffix so the repository's
//! own link check (which scans every `*.md` file) never sees their
//! intentionally broken links. [`materialize`] copies a fixture tree into a
//! temporary directory with the suffix removed.

#![allow(dead_code)]

use std::path::{Path, PathBuf};

/// Copy `tests/fixtures/<name>` into a fresh temp dir, stripping `.in`.
pub fn materialize(name: &str) -> tempfile::TempDir {
    let src = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name);
    let dir = tempfile::tempdir().expect("tempdir");
    copy_tree(&src, dir.path());
    dir
}

fn copy_tree(src: &Path, dst: &Path) {
    std::fs::create_dir_all(dst).expect("mkdir");
    for entry in std::fs::read_dir(src).expect("read fixture dir") {
        let entry = entry.expect("dir entry");
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().into_owned();
        let target = dst.join(name.strip_suffix(".in").unwrap_or(&name));
        if path.is_dir() {
            copy_tree(&path, &target);
        } else {
            std::fs::copy(&path, &target).expect("copy fixture");
        }
    }
}

/// Write `files` (relative path, content) into a fresh temp dir.
pub fn write_tree(files: &[(&str, &str)]) -> tempfile::TempDir {
    let dir = tempfile::tempdir().expect("tempdir");
    for (rel, content) in files {
        let path = dir.path().join(rel);
        std::fs::create_dir_all(path.parent().expect("parent")).expect("mkdir");
        std::fs::write(path, content).expect("write");
    }
    dir
}

/// Path of the built binary.
pub fn binary() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_md-link-checker"))
}
