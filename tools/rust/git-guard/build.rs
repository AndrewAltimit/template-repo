//! Embed `SOURCE_HASH` (this crate's sources + wrapper-common's) for
//! `git --wrapper-integrity` and audit entries.

fn main() {
    wrapper_common::emit_wrapper_source_hash();
}
