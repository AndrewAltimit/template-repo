//! Approved-protocol allowlist: which protocol files an operator has reviewed.
//!
//! The limits in `safety_limits.toml` bound *how much* an agent may command:
//! temperature, volume, flow rate, mix cycles, position, call rate. They say
//! nothing about *what* a protocol does. This module adds the smallest control
//! that addresses the second question: a protocol file may only become the
//! active protocol if its content hash appears in an operator-maintained
//! manifest alongside an approver identity and an approval date.
//!
//! The control is deliberately narrow, and it is worth being precise about
//! what it is not:
//!
//! - It **is** a guarantee that the protocol content the server loads is byte
//!   for byte the content a named human signed off on, and that editing an
//!   approved file invalidates its approval until someone re-approves it.
//! - It is **not** screening of biological targets, sequences, or reagents. It
//!   inspects a hash, never meaning. Deciding whether a protocol is acceptable
//!   at all remains human biosafety review, and for any protocol beyond a
//!   commercially sold teaching kit that review is where screening against an
//!   established framework belongs.
//!
//! The manifest lives with the operator's configuration, is read once at
//! server start, and no tool writes it. A missing, unreadable, or malformed
//! manifest denies every protocol rather than allowing every protocol: see
//! [`ProtocolAllowlist::load`].

use std::collections::HashSet;
use std::fmt;
use std::path::{Path, PathBuf};

use bioforge_types::error::BioForgeError;
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Conventional manifest file name inside the configuration directory.
pub const MANIFEST_FILE_NAME: &str = "approved_protocols.toml";

/// Manifest schema version this build understands.
pub const MANIFEST_VERSION: u32 = 1;

/// Largest manifest file that will be read.
const MAX_MANIFEST_BYTES: u64 = 256 * 1024;

/// Normalize protocol text before hashing, so that an approval survives a
/// checkout with different line endings and does not depend on trailing
/// whitespace.
///
/// The normalization is: drop a leading byte-order mark, convert CRLF and lone
/// CR to LF, strip trailing spaces and tabs from every line, and end the text
/// with exactly one newline (empty text stays empty). Nothing else is touched:
/// comments, ordering, and formatting are all part of the hashed content, so a
/// reviewer's approval covers the file they actually read.
pub fn canonical_text(text: &str) -> String {
    let body = text.strip_prefix('\u{feff}').unwrap_or(text);
    let unified = body.replace("\r\n", "\n").replace('\r', "\n");
    let mut out = String::with_capacity(unified.len() + 1);
    for line in unified.split('\n') {
        out.push_str(line.trim_end_matches([' ', '\t']));
        out.push('\n');
    }
    while out.ends_with("\n\n") {
        out.pop();
    }
    if out == "\n" {
        out.clear();
    }
    out
}

/// SHA-256 of [`canonical_text`], as lowercase hex.
pub fn content_hash(text: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(canonical_text(text).as_bytes());
    format!("{:x}", hasher.finalize())
}

fn is_sha256_hex(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

/// Whether an approver field still holds template text such as `<name>`.
fn is_placeholder(approved_by: &str) -> bool {
    approved_by.contains('<') || approved_by.contains('>')
}

/// One reviewed protocol: a content hash, who approved it, and when.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Approval {
    /// Protocol id as `load_protocol` addresses it (`name` or `custom/name`).
    pub protocol_id: String,
    /// Lowercase hex SHA-256 of the file's [`canonical_text`].
    pub sha256: String,
    /// Who reviewed and approved the protocol. Free text, recorded verbatim.
    pub approved_by: String,
    /// Date of approval as a quoted `"YYYY-MM-DD"` string.
    pub approved_on: NaiveDate,
    /// Optional note about the review: what was checked, by which process.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub review_note: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct ManifestFile {
    version: u32,
    #[serde(default)]
    approved: Vec<Approval>,
}

/// A parsed and internally consistent approved-protocol manifest.
#[derive(Debug, Clone, Default)]
pub struct ApprovedProtocols {
    entries: Vec<Approval>,
}

impl ApprovedProtocols {
    /// Parse manifest TOML, rejecting anything ambiguous: an unsupported
    /// schema version, an unknown field, a hash that is not 64 lowercase hex
    /// characters, a missing approver, or two entries for the same protocol.
    pub fn parse(text: &str) -> Result<Self, BioForgeError> {
        let file: ManifestFile = toml::from_str(text).map_err(|e| {
            BioForgeError::ConfigError(format!("invalid approved-protocol manifest: {e}"))
        })?;
        if file.version != MANIFEST_VERSION {
            return Err(BioForgeError::ConfigError(format!(
                "approved-protocol manifest version {} is not supported (this build expects {MANIFEST_VERSION})",
                file.version
            )));
        }

        let mut seen: HashSet<String> = HashSet::new();
        for entry in &file.approved {
            let id = entry.protocol_id.as_str();
            if id.is_empty() || id.chars().any(char::is_whitespace) {
                return Err(BioForgeError::ConfigError(format!(
                    "approved-protocol manifest: protocol_id {id:?} must be non-empty and contain no whitespace"
                )));
            }
            if !is_sha256_hex(&entry.sha256) {
                return Err(BioForgeError::ConfigError(format!(
                    "approved-protocol manifest: sha256 for '{id}' must be 64 lowercase hex characters"
                )));
            }
            if entry.approved_by.trim().is_empty() {
                return Err(BioForgeError::ConfigError(format!(
                    "approved-protocol manifest: approved_by for '{id}' must name the approver"
                )));
            }
            if is_placeholder(&entry.approved_by) {
                return Err(BioForgeError::ConfigError(format!(
                    "approved-protocol manifest: approved_by for '{id}' is still a template placeholder; \
                     the lab's responsible reviewer must record their own name"
                )));
            }
            if !seen.insert(entry.protocol_id.clone()) {
                return Err(BioForgeError::ConfigError(format!(
                    "approved-protocol manifest: duplicate entry for '{id}'"
                )));
            }
        }

        Ok(Self {
            entries: file.approved,
        })
    }

    /// Every approval in the manifest, in file order.
    pub fn entries(&self) -> &[Approval] {
        &self.entries
    }

    /// The approval for `protocol_id`, if the manifest has one.
    pub fn get(&self, protocol_id: &str) -> Option<&Approval> {
        self.entries.iter().find(|e| e.protocol_id == protocol_id)
    }

    /// Number of approved protocols.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the manifest approves nothing (which denies every protocol).
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// Why a protocol was not allowed to load.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApprovalDenial {
    /// The manifest is missing or unusable, so nothing is approved.
    ManifestUnavailable {
        /// Path the manifest was expected at.
        source: String,
        /// Why it could not be used.
        reason: String,
    },
    /// The manifest has no entry for this protocol id.
    NotApproved {
        /// Protocol that was requested.
        protocol_id: String,
        /// Hash of the file as it is on disk now.
        computed_sha256: String,
        /// Path of the manifest consulted.
        source: String,
    },
    /// The file on disk differs from the approved content.
    ContentChanged {
        /// Protocol that was requested.
        protocol_id: String,
        /// Hash the operator approved.
        approved_sha256: String,
        /// Hash of the file as it is on disk now.
        computed_sha256: String,
        /// Path of the manifest consulted.
        source: String,
    },
}

impl fmt::Display for ApprovalDenial {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ManifestUnavailable { source, reason } => write!(
                f,
                "no usable approved-protocol manifest at {source} ({reason}); \
                 every protocol is denied until an operator provides one"
            ),
            Self::NotApproved {
                protocol_id,
                computed_sha256,
                source,
            } => write!(
                f,
                "protocol '{protocol_id}' is not in the approved-protocol manifest {source}; \
                 an operator must review it and add an entry with sha256 = \"{computed_sha256}\""
            ),
            Self::ContentChanged {
                protocol_id,
                approved_sha256,
                computed_sha256,
                source,
            } => write!(
                f,
                "protocol '{protocol_id}' has changed since it was approved in {source} \
                 (approved {approved_sha256}, on disk {computed_sha256}); \
                 an operator must review the change and update the entry"
            ),
        }
    }
}

impl std::error::Error for ApprovalDenial {}

impl From<ApprovalDenial> for BioForgeError {
    fn from(d: ApprovalDenial) -> Self {
        BioForgeError::ProtocolError(d.to_string())
    }
}

/// The allowlist as a running server holds it: either a parsed manifest, or a
/// recorded reason why there is none, which denies everything.
#[derive(Debug, Clone)]
pub struct ProtocolAllowlist {
    source: PathBuf,
    state: Result<ApprovedProtocols, String>,
}

impl ProtocolAllowlist {
    /// Build an allowlist from an already parsed manifest.
    pub fn new(source: impl Into<PathBuf>, manifest: ApprovedProtocols) -> Self {
        Self {
            source: source.into(),
            state: Ok(manifest),
        }
    }

    /// Build an allowlist that denies every protocol, recording why.
    pub fn unavailable(source: impl Into<PathBuf>, reason: impl Into<String>) -> Self {
        Self {
            source: source.into(),
            state: Err(reason.into()),
        }
    }

    /// Read the manifest at `path`.
    ///
    /// This never fails: a missing, oversized, unreadable, or malformed
    /// manifest produces an allowlist that denies every protocol, so losing
    /// the manifest cannot silently turn the control off. The caller is
    /// expected to surface [`Self::unavailable_reason`] at startup.
    pub fn load(path: impl Into<PathBuf>) -> Self {
        let path = path.into();
        match read_capped(&path) {
            Ok(text) => match ApprovedProtocols::parse(&text) {
                Ok(manifest) => Self::new(path, manifest),
                Err(e) => Self::unavailable(path, e.to_string()),
            },
            Err(reason) => Self::unavailable(path, reason),
        }
    }

    /// Path the manifest was read from (or expected at).
    pub fn source(&self) -> &Path {
        &self.source
    }

    /// Whether a usable manifest was loaded.
    pub fn is_available(&self) -> bool {
        self.state.is_ok()
    }

    /// Why the manifest is unusable, if it is.
    pub fn unavailable_reason(&self) -> Option<&str> {
        self.state.as_ref().err().map(String::as_str)
    }

    /// Number of approved protocols (0 when no manifest is available).
    pub fn approved_count(&self) -> usize {
        self.state.as_ref().map_or(0, ApprovedProtocols::len)
    }

    /// The approval entry for `protocol_id`, if any.
    pub fn get(&self, protocol_id: &str) -> Option<&Approval> {
        self.state.as_ref().ok()?.get(protocol_id)
    }

    /// Decide whether `text` may be loaded as `protocol_id`.
    ///
    /// The hash is computed from the text the caller has already read, so the
    /// check applies to the exact bytes that will be parsed and executed.
    pub fn check(&self, protocol_id: &str, text: &str) -> Result<&Approval, ApprovalDenial> {
        let computed = content_hash(text);
        let source = self.source.display().to_string();
        let manifest = match &self.state {
            Ok(m) => m,
            Err(reason) => {
                return Err(ApprovalDenial::ManifestUnavailable {
                    source,
                    reason: reason.clone(),
                });
            },
        };
        let Some(entry) = manifest.get(protocol_id) else {
            return Err(ApprovalDenial::NotApproved {
                protocol_id: protocol_id.to_string(),
                computed_sha256: computed,
                source,
            });
        };
        if entry.sha256 == computed {
            Ok(entry)
        } else {
            Err(ApprovalDenial::ContentChanged {
                protocol_id: protocol_id.to_string(),
                approved_sha256: entry.sha256.clone(),
                computed_sha256: computed,
                source,
            })
        }
    }
}

fn read_capped(path: &Path) -> Result<String, String> {
    let meta =
        std::fs::metadata(path).map_err(|e| format!("cannot stat {}: {e}", path.display()))?;
    if !meta.is_file() {
        return Err(format!("{} is not a file", path.display()));
    }
    if meta.len() > MAX_MANIFEST_BYTES {
        return Err(format!(
            "{} is {} bytes; the limit is {MAX_MANIFEST_BYTES}",
            path.display(),
            meta.len()
        ));
    }
    std::fs::read_to_string(path).map_err(|e| format!("cannot read {}: {e}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROTOCOL: &str = "name = \"p\"\nversion = \"1.0\"\ndescription = \"d\"\n";

    fn manifest_for(text: &str) -> String {
        format!(
            "version = 1\n\n[[approved]]\nprotocol_id = \"p\"\nsha256 = \"{}\"\n\
             approved_by = \"operator\"\napproved_on = \"2026-09-27\"\n",
            content_hash(text)
        )
    }

    #[test]
    fn placeholder_approver_is_rejected() {
        let manifest = manifest_for(PROTOCOL).replace(
            "approved_by = \"operator\"",
            "approved_by = \"<name and role of your lab's responsible biosafety reviewer>\"",
        );
        let err = ApprovedProtocols::parse(&manifest).unwrap_err();
        assert!(err.to_string().contains("placeholder"));
    }

    // -- Hashing --

    #[test]
    fn hash_is_stable_and_lowercase_hex() {
        let h = content_hash(PROTOCOL);
        assert_eq!(h.len(), 64);
        assert!(is_sha256_hex(&h));
        assert_eq!(h, content_hash(PROTOCOL));
    }

    #[test]
    fn hash_ignores_line_endings_bom_and_trailing_whitespace() {
        let crlf = PROTOCOL.replace('\n', "\r\n");
        let padded = PROTOCOL.replace('\n', "  \t\n");
        let bom = format!("\u{feff}{PROTOCOL}");
        let extra_newlines = format!("{PROTOCOL}\n\n\n");
        let expected = content_hash(PROTOCOL);
        for variant in [crlf, padded, bom, extra_newlines] {
            assert_eq!(content_hash(&variant), expected);
        }
    }

    #[test]
    fn hash_changes_on_any_content_edit() {
        let edited = PROTOCOL.replace("1.0", "1.1");
        assert_ne!(content_hash(&edited), content_hash(PROTOCOL));
        // Comments are content: a reviewer approved the file they read.
        let commented = format!("# harmless\n{PROTOCOL}");
        assert_ne!(content_hash(&commented), content_hash(PROTOCOL));
    }

    #[test]
    fn canonical_text_of_empty_input_is_empty() {
        assert_eq!(canonical_text(""), "");
        assert_eq!(canonical_text("\n\n"), "");
    }

    // -- Manifest parsing --

    #[test]
    fn parses_a_well_formed_manifest() {
        let m = ApprovedProtocols::parse(&manifest_for(PROTOCOL)).unwrap();
        assert_eq!(m.len(), 1);
        let e = m.get("p").unwrap();
        assert_eq!(e.approved_by, "operator");
        assert_eq!(e.approved_on.to_string(), "2026-09-27");
        assert!(m.get("other").is_none());
    }

    #[test]
    fn empty_manifest_parses_and_approves_nothing() {
        let m = ApprovedProtocols::parse("version = 1\n").unwrap();
        assert!(m.is_empty());
    }

    #[test]
    fn rejects_unsupported_version() {
        let bad = manifest_for(PROTOCOL).replace("version = 1", "version = 2");
        let err = ApprovedProtocols::parse(&bad).unwrap_err().to_string();
        assert!(err.contains("not supported"), "{err}");
    }

    #[test]
    fn rejects_malformed_hash() {
        for bad_hash in ["deadbeef", &"A".repeat(64), &"z".repeat(64)] {
            let bad = manifest_for(PROTOCOL).replace(&content_hash(PROTOCOL), bad_hash);
            let err = ApprovedProtocols::parse(&bad).unwrap_err().to_string();
            assert!(err.contains("sha256"), "{err}");
        }
    }

    #[test]
    fn rejects_missing_approver_and_duplicates() {
        let blank = manifest_for(PROTOCOL).replace("\"operator\"", "\"  \"");
        assert!(
            ApprovedProtocols::parse(&blank)
                .unwrap_err()
                .to_string()
                .contains("approved_by")
        );

        let dup = format!(
            "{}{}",
            manifest_for(PROTOCOL),
            manifest_for(PROTOCOL).replace("version = 1\n\n", "")
        );
        assert!(
            ApprovedProtocols::parse(&dup)
                .unwrap_err()
                .to_string()
                .contains("duplicate")
        );
    }

    #[test]
    fn rejects_unknown_fields_rather_than_ignoring_them() {
        // A typo in a field name must fail closed, not silently drop the
        // constraint it was meant to express.
        let typo = manifest_for(PROTOCOL).replace("sha256", "sha_256");
        assert!(ApprovedProtocols::parse(&typo).is_err());
    }

    #[test]
    fn rejects_missing_version_and_broken_toml() {
        assert!(ApprovedProtocols::parse("[[approved]]\n").is_err());
        assert!(ApprovedProtocols::parse("version = ").is_err());
    }

    // -- Allowlist decisions --

    #[test]
    fn approved_protocol_passes() {
        let list = ProtocolAllowlist::new(
            "manifest.toml",
            ApprovedProtocols::parse(&manifest_for(PROTOCOL)).unwrap(),
        );
        let entry = list.check("p", PROTOCOL).expect("approved");
        assert_eq!(entry.approved_by, "operator");
        assert!(list.is_available());
        assert_eq!(list.approved_count(), 1);
    }

    #[test]
    fn modified_protocol_is_denied() {
        let list = ProtocolAllowlist::new(
            "manifest.toml",
            ApprovedProtocols::parse(&manifest_for(PROTOCOL)).unwrap(),
        );
        let edited = PROTOCOL.replace("\"d\"", "\"edited after approval\"");
        match list.check("p", &edited).unwrap_err() {
            ApprovalDenial::ContentChanged {
                approved_sha256,
                computed_sha256,
                ..
            } => {
                assert_eq!(approved_sha256, content_hash(PROTOCOL));
                assert_eq!(computed_sha256, content_hash(&edited));
            },
            other => panic!("unexpected denial: {other}"),
        }
    }

    #[test]
    fn unlisted_protocol_is_denied_with_its_hash() {
        let list = ProtocolAllowlist::new(
            "manifest.toml",
            ApprovedProtocols::parse(&manifest_for(PROTOCOL)).unwrap(),
        );
        let msg = list.check("other", PROTOCOL).unwrap_err().to_string();
        assert!(
            msg.contains("not in the approved-protocol manifest"),
            "{msg}"
        );
        assert!(msg.contains(&content_hash(PROTOCOL)), "{msg}");
    }

    #[test]
    fn missing_manifest_fails_closed() {
        let dir = tempfile::tempdir().unwrap();
        let list = ProtocolAllowlist::load(dir.path().join(MANIFEST_FILE_NAME));
        assert!(!list.is_available());
        assert_eq!(list.approved_count(), 0);
        assert!(list.unavailable_reason().is_some());
        assert!(matches!(
            list.check("p", PROTOCOL).unwrap_err(),
            ApprovalDenial::ManifestUnavailable { .. }
        ));
    }

    #[test]
    fn malformed_manifest_fails_closed() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(MANIFEST_FILE_NAME);
        std::fs::write(&path, "version = 1\n[[approved]]\nprotocol_id = \"p\"\n").unwrap();
        let list = ProtocolAllowlist::load(&path);
        assert!(!list.is_available());
        assert!(list.check("p", PROTOCOL).is_err());
    }

    #[test]
    fn loads_a_manifest_from_disk() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(MANIFEST_FILE_NAME);
        std::fs::write(&path, manifest_for(PROTOCOL)).unwrap();
        let list = ProtocolAllowlist::load(&path);
        assert!(list.is_available(), "{:?}", list.unavailable_reason());
        assert_eq!(list.source(), path);
        assert!(list.check("p", PROTOCOL).is_ok());
    }
}
