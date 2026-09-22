//! Embed a hash of wrapper-common's own sources as `COMMON_SOURCE_HASH`.
//!
//! The wrappers mix this value into their own `SOURCE_HASH`, so a change to
//! the shared security logic in this crate changes every wrapper's reported
//! integrity hash.

#[path = "src/source_hash.rs"]
mod source_hash;

fn main() {
    println!("cargo:rerun-if-changed=src");
    println!("cargo:rerun-if-changed=Cargo.toml");

    let crate_dir = std::path::PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR not set"),
    );
    let hash = source_hash::hash_crate(&crate_dir, &[]);
    source_hash::write_const("common_hash.rs", "COMMON_SOURCE_HASH", &hash);
}
