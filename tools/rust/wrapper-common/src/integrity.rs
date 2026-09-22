//! Compile-time integrity identification.
//!
//! Each wrapper embeds a SHA-256 hash of its own sources *and* of this
//! crate's sources (see [`crate::emit_wrapper_source_hash`]). The hash is a
//! version identifier for baseline comparison by
//! `automation/setup/security/verify-wrapper-guard.sh`; it is not runtime
//! tamper detection (a modified binary can print anything).

include!(concat!(env!("OUT_DIR"), "/common_hash.rs"));

/// The flag every wrapper answers before doing anything else.
pub const INTEGRITY_FLAG: &str = "--wrapper-integrity";

/// If the first argument is `--wrapper-integrity`, print the wrapper name,
/// source hash, and binary path (one `key=value` per line) and return `true`;
/// the caller should then exit 0.
pub fn check_integrity_flag(args: &[String], wrapper_name: &str, source_hash: &str) -> bool {
    if args.first().map(String::as_str) != Some(INTEGRITY_FLAG) {
        return false;
    }
    let binary = std::env::current_exe()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_else(|_| "unknown".to_string());
    println!("wrapper={wrapper_name}");
    println!("source_hash={source_hash}");
    println!("common_hash={COMMON_SOURCE_HASH}");
    println!("binary={binary}");
    true
}

/// Whether `hash` looks like a SHA-256 hex digest.
pub fn is_valid_hash(hash: &str) -> bool {
    hash.len() == 64 && hash.bytes().all(|b| b.is_ascii_hexdigit())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn integrity_flag_matches_only_first_arg() {
        assert!(check_integrity_flag(
            &["--wrapper-integrity".to_string()],
            "test",
            "abc"
        ));
        assert!(!check_integrity_flag(
            &["status".to_string(), "--wrapper-integrity".to_string()],
            "test",
            "abc"
        ));
        assert!(!check_integrity_flag(&[], "test", "abc"));
    }

    #[test]
    fn hash_validation() {
        assert!(is_valid_hash(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ));
        assert!(!is_valid_hash("too_short"));
        assert!(!is_valid_hash(
            "g3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ));
    }

    #[test]
    fn common_hash_is_embedded() {
        assert!(is_valid_hash(COMMON_SOURCE_HASH));
    }
}
