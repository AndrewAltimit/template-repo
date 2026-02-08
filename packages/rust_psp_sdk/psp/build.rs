use std::{env, path::Path};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=libunwind.a");
    println!("cargo:rerun-if-env-changed=RUSTFLAGS");
    // Suppress unexpected_cfgs warnings for bootstrap cfg used by std internals.
    println!("cargo::rustc-check-cfg=cfg(bootstrap)");

    if env::var("CARGO_FEATURE_STUB_ONLY").is_ok() {
        return;
    }

    // Figure out whether to use the LTO libunwind, or the regular one.
    let rustflags = env::var("CARGO_ENCODED_RUSTFLAGS").unwrap_or_default();
    let libunwind = if rustflags
        .split('\x1f')
        .any(|flags| flags.starts_with("-Clinker-plugin-lto"))
    {
        "./libunwind_lto.a"
    } else {
        "./libunwind.a"
    };

    let out_dir = env::var("OUT_DIR").expect("OUT_DIR not set by cargo");
    let out_file = Path::new(&out_dir).join("libunwind.a");
    std::fs::copy(libunwind, &out_file).unwrap_or_else(|e| {
        panic!(
            "failed to copy {} to {}: {e}",
            libunwind,
            out_file.display()
        )
    });

    println!("cargo:rustc-link-lib=static=unwind");
    println!("cargo:rustc-link-search=native={}", out_dir);
}
