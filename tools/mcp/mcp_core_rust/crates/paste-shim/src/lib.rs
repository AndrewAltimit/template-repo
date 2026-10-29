//! Stand-in for the unmaintained `paste` crate (RUSTSEC-2024-0436).
//!
//! `tokenizers` 0.23 (via `fastembed`) depends on `paste` unconditionally and
//! only calls `paste::paste!`. Servers that embed text patch `paste` to this
//! crate, which re-exports the macro from `pastey`, its maintained drop-in
//! successor. Remove the shim and the `[patch.crates-io]` entries once
//! `fastembed` moves to `tokenizers` 1.0, which no longer uses `paste`.

pub use pastey::paste;

#[cfg(test)]
mod tests {
    // Mirrors how tokenizers uses the macro: identifier concatenation and
    // string concatenation inside an attribute, from within `macro_rules!`.
    macro_rules! tagged {
        ($name:ident) => {
            crate::paste! {
                #[doc = $name "Deserializer"]
                #[allow(dead_code)]
                struct [<$name Deserializer>];

                fn [<$name:snake _doc>]() -> &'static str {
                    stringify!([<$name Deserializer>])
                }
            }
        };
    }

    tagged!(Bpe);

    #[test]
    fn concatenates_identifiers_and_attribute_strings() {
        assert_eq!(bpe_doc(), "BpeDeserializer");
    }
}
