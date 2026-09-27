//! Protocol file discovery, loading and step-level safety validation.
//!
//! Protocols live in a protocols directory (by default
//! `packages/bioforge/protocols`): `<dir>/<id>.toml` for curated protocols
//! and `<dir>/custom/<id>.toml` for user-authored ones, addressed as
//! `custom/<id>`. Ids are restricted to a filename-safe alphabet and the
//! resolved path is re-checked after canonicalization, so a protocol id can
//! never reach outside the protocols directory.
//!
//! Finding a file is not permission to run it: whether a protocol may become
//! the active protocol is decided by the approved-protocol manifest (see
//! [`bioforge_protocol::approval`] and [`crate::lab::Lab::load_protocol`]).

use std::path::{Path, PathBuf};

use bioforge_protocol::approval::{ProtocolAllowlist, content_hash};
use bioforge_safety::SafetyEnforcer;
use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::{Protocol, StepAction};
use serde::Serialize;

use crate::error::{LabError, LabResult, invalid};
use crate::validate;

/// Largest protocol file the server will parse.
const MAX_PROTOCOL_BYTES: u64 = 256 * 1024;
/// Upper bound for `request_human_action.timeout_min` (24 hours).
pub const MAX_HUMAN_TIMEOUT_MIN: u64 = 24 * 60;
/// Subdirectory for user-authored protocols.
const CUSTOM_DIR: &str = "custom";

/// Locates protocol TOML files under a root directory.
#[derive(Debug, Clone)]
pub struct ProtocolStore {
    root: PathBuf,
}

/// One entry returned by [`ProtocolStore::list`].
#[derive(Debug, Default, Serialize)]
pub struct ProtocolListing {
    /// Id to pass to `load_protocol`.
    pub protocol_id: String,
    /// Protocol `name` field, if the file parsed.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    /// Protocol `description` field, if the file parsed.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    /// Number of steps, if the file parsed.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub steps: Option<usize>,
    /// Content hash of the file as it is on disk, if it could be read.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sha256: Option<String>,
    /// Whether this exact content is in the approved-protocol manifest.
    /// `load_protocol` refuses anything that is not.
    pub approved: bool,
    /// Who approved this content, when it is approved.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub approved_by: Option<String>,
    /// When it was approved, when it is approved.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub approved_on: Option<String>,
    /// Read or parse error, if the file could not be read or did not parse.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

/// A problem found while validating a protocol step against safety limits.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct StepIssue {
    /// Step id (0 for protocol-level issues).
    pub step_id: u32,
    /// Step name (or `"<protocol>"` for protocol-level issues).
    pub step_name: String,
    /// What is wrong.
    pub message: String,
}

impl ProtocolStore {
    /// Create a store rooted at `root`. The directory need not exist yet.
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    /// The configured protocols directory.
    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Map a protocol id (`name` or `custom/name`, optional `.toml` suffix)
    /// to a path under the root. Pure string handling; no I/O.
    pub fn path_for(&self, protocol_id: &str) -> LabResult<PathBuf> {
        let id = protocol_id.strip_suffix(".toml").unwrap_or(protocol_id);
        let (sub, stem) = match id.split_once('/') {
            Some((CUSTOM_DIR, stem)) => (Some(CUSTOM_DIR), stem),
            Some(_) => {
                return Err(invalid(format!(
                    "protocol_id '{protocol_id}' is invalid: only the 'custom/' prefix is allowed"
                )));
            },
            None => (None, id),
        };
        validate::identifier("protocol_id", stem).map_err(invalid)?;
        let mut path = self.root.clone();
        if let Some(sub) = sub {
            path.push(sub);
        }
        path.push(format!("{stem}.toml"));
        Ok(path)
    }

    /// Read a protocol file's raw text by id, after the path, type and size
    /// checks. The text is returned unparsed so the caller can hash exactly
    /// the bytes it is about to parse.
    pub async fn read_text(&self, protocol_id: &str) -> LabResult<String> {
        let path = self.path_for(protocol_id)?;
        let meta = match tokio::fs::metadata(&path).await {
            Ok(m) => m,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                return Err(invalid(format!(
                    "protocol '{protocol_id}' not found (looked for {}); use list_protocols to see available ids",
                    path.display()
                )));
            },
            Err(e) => {
                return Err(LabError::Refused(BioForgeError::ProtocolError(format!(
                    "cannot stat {}: {e}",
                    path.display()
                ))));
            },
        };
        if !meta.is_file() {
            return Err(invalid(format!("{} is not a file", path.display())));
        }
        if meta.len() > MAX_PROTOCOL_BYTES {
            return Err(invalid(format!(
                "protocol file is {} bytes; the limit is {MAX_PROTOCOL_BYTES}",
                meta.len()
            )));
        }
        // Defense in depth against symlinks pointing outside the root.
        if let (Ok(root), Ok(file)) = (
            tokio::fs::canonicalize(&self.root).await,
            tokio::fs::canonicalize(&path).await,
        ) && !file.starts_with(&root)
        {
            return Err(invalid(format!(
                "protocol '{protocol_id}' resolves outside the protocols directory"
            )));
        }

        tokio::fs::read_to_string(&path).await.map_err(|e| {
            LabError::Refused(BioForgeError::ProtocolError(format!(
                "cannot read {}: {e}",
                path.display()
            )))
        })
    }

    /// Parse text obtained from [`Self::read_text`], tagging failures with the
    /// file path the text came from.
    pub fn parse_named(&self, protocol_id: &str, text: &str) -> LabResult<Protocol> {
        parse_protocol(text).map_err(|e| {
            let path = self
                .path_for(protocol_id)
                .map(|p| p.display().to_string())
                .unwrap_or_else(|_| protocol_id.to_string());
            LabError::Refused(BioForgeError::ProtocolError(format!("{path}: {e}")))
        })
    }

    /// List every protocol file under the root and `root/custom`, reporting
    /// its name, step count, content hash and approval status.
    pub async fn list(&self, allowlist: &ProtocolAllowlist) -> LabResult<Vec<ProtocolListing>> {
        let mut out = Vec::new();
        for (prefix, dir) in [
            ("", self.root.clone()),
            ("custom/", self.root.join(CUSTOM_DIR)),
        ] {
            let mut entries = match tokio::fs::read_dir(&dir).await {
                Ok(rd) => rd,
                Err(e) if e.kind() == std::io::ErrorKind::NotFound && !prefix.is_empty() => {
                    continue;
                },
                Err(e) => {
                    return Err(LabError::Refused(BioForgeError::ProtocolError(format!(
                        "cannot list protocols directory {}: {e}",
                        dir.display()
                    ))));
                },
            };
            while let Ok(Some(entry)) = entries.next_entry().await {
                let path = entry.path();
                if path.extension().and_then(|e| e.to_str()) != Some("toml") {
                    continue;
                }
                let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
                    continue;
                };
                if validate::identifier("protocol_id", stem).is_err() {
                    continue;
                }
                let id = format!("{prefix}{stem}");
                let listing = match self.read_text(&id).await {
                    Ok(text) => {
                        let sha256 = content_hash(&text);
                        // An approval only counts for the content it covers.
                        let approval = allowlist.get(&id).filter(|a| a.sha256 == sha256);
                        let mut listing = ProtocolListing {
                            sha256: Some(sha256),
                            approved: approval.is_some(),
                            approved_by: approval.map(|a| a.approved_by.clone()),
                            approved_on: approval.map(|a| a.approved_on.to_string()),
                            protocol_id: id,
                            ..ProtocolListing::default()
                        };
                        match self.parse_named(&listing.protocol_id, &text) {
                            Ok(p) => {
                                listing.name = Some(p.name);
                                listing.description = Some(p.description);
                                listing.steps = Some(p.steps.len());
                            },
                            Err(e) => listing.error = Some(e.to_string()),
                        }
                        listing
                    },
                    Err(e) => ProtocolListing {
                        protocol_id: id,
                        error: Some(e.to_string()),
                        ..ProtocolListing::default()
                    },
                };
                out.push(listing);
            }
        }
        out.sort_by(|a, b| a.protocol_id.cmp(&b.protocol_id));
        Ok(out)
    }
}

/// Parse protocol TOML text.
pub fn parse_protocol(text: &str) -> Result<Protocol, String> {
    toml::from_str::<Protocol>(text).map_err(|e| format!("invalid protocol TOML: {e}"))
}

/// Record the error of a failed check, if any.
fn note<E: ToString>(errs: &mut Vec<String>, r: Result<(), E>) {
    if let Err(e) = r {
        errs.push(e.to_string());
    }
}

/// Short snake_case name of a step action, as used in the TOML `type` field.
pub fn action_type(action: &StepAction) -> &'static str {
    match action {
        StepAction::Dispense { .. } => "dispense",
        StepAction::Aspirate { .. } => "aspirate",
        StepAction::Mix { .. } => "mix",
        StepAction::MoveTo { .. } => "move_to",
        StepAction::SetTemperature { .. } => "set_temperature",
        StepAction::HeatShock { .. } => "heat_shock",
        StepAction::Incubate { .. } => "incubate",
        StepAction::CaptureImage { .. } => "capture_image",
        StepAction::CountColonies { .. } => "count_colonies",
        StepAction::Wait { .. } => "wait",
        StepAction::RequestHumanAction { .. } => "request_human_action",
    }
}

/// Validate every step of `protocol` against the configured safety limits
/// without touching any stateful counters.
///
/// Returns all issues found (empty means the protocol is runnable within the
/// current limits). Structural problems (no steps, duplicate or unordered
/// ids) are reported as protocol-level issues with `step_id` 0.
pub fn validate_steps(protocol: &Protocol, enforcer: &SafetyEnforcer) -> Vec<StepIssue> {
    let mut issues = Vec::new();
    if let Err(e) = bioforge_protocol::validate_protocol(protocol) {
        issues.push(StepIssue {
            step_id: 0,
            step_name: "<protocol>".into(),
            message: e.to_string(),
        });
    }

    let limits = enforcer.limits();
    let max_duration_s = limits.operations.max_incubation_hours * 3600.0;
    let mut total_dispense_ul = 0.0;

    for step in &protocol.steps {
        let mut errs: Vec<String> = Vec::new();

        match &step.action {
            StepAction::Dispense {
                target,
                volume_ul,
                reagent,
                flow_rate,
            } => {
                note(&mut errs, validate::label("target", target));
                note(&mut errs, validate::label("reagent", reagent));
                note(&mut errs, enforcer.validate_volume(*volume_ul));
                if let Some(r) = flow_rate {
                    note(&mut errs, enforcer.validate_flow_rate(*r));
                }
                if volume_ul.is_finite() && *volume_ul > 0.0 {
                    total_dispense_ul += volume_ul;
                }
            },
            StepAction::Aspirate {
                source,
                volume_ul,
                flow_rate,
            } => {
                note(&mut errs, validate::label("source", source));
                note(&mut errs, enforcer.validate_volume(*volume_ul));
                if let Some(r) = flow_rate {
                    note(&mut errs, enforcer.validate_flow_rate(*r));
                }
            },
            StepAction::Mix {
                target,
                volume_ul,
                cycles,
                flow_rate,
            } => {
                note(&mut errs, validate::label("target", target));
                note(&mut errs, enforcer.validate_volume(*volume_ul));
                note(&mut errs, enforcer.validate_mix_cycles(*cycles));
                if let Some(r) = flow_rate {
                    note(&mut errs, enforcer.validate_flow_rate(*r));
                }
            },
            StepAction::MoveTo { x_mm, y_mm, z_mm } => {
                let z = z_mm.unwrap_or_else(|| enforcer.safe_travel_height());
                note(&mut errs, enforcer.validate_position(*x_mm, *y_mm, z));
            },
            StepAction::SetTemperature {
                target_c,
                hold_seconds,
                ..
            } => {
                note(&mut errs, enforcer.validate_temperature(*target_c));
                if let Some(h) = hold_seconds {
                    note(
                        &mut errs,
                        enforcer.validate_duration_s(*h as f64, max_duration_s),
                    );
                }
            },
            StepAction::HeatShock {
                ramp_to_c,
                hold_s,
                return_to_c,
            } => {
                note(&mut errs, enforcer.validate_temperature(*ramp_to_c));
                note(&mut errs, enforcer.validate_temperature(*return_to_c));
                note(&mut errs, enforcer.validate_heat_shock_hold_s(*hold_s));
            },
            StepAction::Incubate {
                target_c,
                duration_hours,
                ..
            } => {
                note(&mut errs, enforcer.validate_temperature(*target_c));
                note(
                    &mut errs,
                    enforcer.validate_incubation_hours(*duration_hours),
                );
            },
            StepAction::CaptureImage { plate_id, .. } => {
                note(&mut errs, validate::identifier("plate_id", plate_id));
            },
            StepAction::CountColonies { plate_id, image_id } => {
                note(&mut errs, validate::identifier("plate_id", plate_id));
                note(&mut errs, validate::identifier("image_id", image_id));
            },
            StepAction::Wait { seconds, .. } => {
                note(
                    &mut errs,
                    enforcer.validate_duration_s(*seconds as f64, max_duration_s),
                );
            },
            StepAction::RequestHumanAction {
                description,
                timeout_min,
            } => {
                note(&mut errs, validate::description("description", description));
                if *timeout_min == 0 || *timeout_min > MAX_HUMAN_TIMEOUT_MIN {
                    errs.push(format!(
                        "timeout_min {timeout_min} must be between 1 and {MAX_HUMAN_TIMEOUT_MIN}"
                    ));
                }
            },
        }

        for message in errs {
            issues.push(StepIssue {
                step_id: step.id,
                step_name: step.name.clone(),
                message,
            });
        }
    }

    let max_total_ul = limits.volume.max_total_ml * 1000.0;
    if total_dispense_ul > max_total_ul {
        issues.push(StepIssue {
            step_id: 0,
            step_name: "<protocol>".into(),
            message: format!(
                "protocol dispenses {total_dispense_ul:.1} uL in total, exceeding the per-run limit of {max_total_ul:.1} uL"
            ),
        });
    }

    issues
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::tests::{test_bounds, test_limits};

    fn enforcer() -> SafetyEnforcer {
        SafetyEnforcer::new(test_limits(), test_bounds())
    }

    const GOOD: &str = r#"
name = "good"
version = "1.0"
description = "valid test protocol"

[[steps]]
id = 1
name = "Dispense"
human_gate = false
[steps.action]
type = "dispense"
target = "plate_1:A1"
volume_ul = 100.0
reagent = "lb"

[[steps]]
id = 2
name = "Gate"
human_gate = true
[steps.action]
type = "request_human_action"
description = "Load plates"
timeout_min = 5
"#;

    fn package_protocols() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../packages/bioforge/protocols")
    }

    fn package_manifest() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../packages/bioforge/config")
            .join(bioforge_protocol::approval::MANIFEST_FILE_NAME)
    }

    /// An allowlist approving `text` under `id`, as an operator would.
    fn allowlist_for(id: &str, text: &str) -> ProtocolAllowlist {
        let manifest = format!(
            "version = 1\n\n[[approved]]\nprotocol_id = \"{id}\"\nsha256 = \"{}\"\n\
             approved_by = \"test operator\"\napproved_on = \"2026-09-27\"\n",
            content_hash(text)
        );
        ProtocolAllowlist::new(
            "test-manifest.toml",
            bioforge_protocol::approval::ApprovedProtocols::parse(&manifest).unwrap(),
        )
    }

    fn deny_all() -> ProtocolAllowlist {
        ProtocolAllowlist::unavailable("test-manifest.toml", "not present in this test")
    }

    #[test]
    fn path_for_accepts_plain_and_custom_ids() {
        let s = ProtocolStore::new("/p");
        assert!(s.path_for("odin").unwrap().ends_with("odin.toml"));
        assert!(s.path_for("odin.toml").unwrap().ends_with("odin.toml"));
        let c = s.path_for("custom/mine").unwrap();
        assert!(c.ends_with(Path::new("custom").join("mine.toml")));
    }

    #[test]
    fn path_for_rejects_traversal() {
        let s = ProtocolStore::new("/p");
        for bad in [
            "../secret",
            "custom/../../x",
            "a/b",
            "..",
            "",
            "/etc/passwd",
            "c:\\x",
            "custom/",
        ] {
            assert!(
                matches!(s.path_for(bad), Err(LabError::Invalid(_))),
                "should reject {bad:?}"
            );
        }
    }

    #[test]
    fn good_protocol_has_no_issues() {
        let p = parse_protocol(GOOD).unwrap();
        assert!(validate_steps(&p, &enforcer()).is_empty());
    }

    #[test]
    fn reports_out_of_range_steps() {
        let text = GOOD
            .replace("volume_ul = 100.0", "volume_ul = 5000.0")
            .replace("timeout_min = 5", "timeout_min = 0");
        let p = parse_protocol(&text).unwrap();
        let issues = validate_steps(&p, &enforcer());
        assert_eq!(issues.len(), 2, "{issues:?}");
        assert_eq!(issues[0].step_id, 1);
        assert!(issues[0].message.contains("volume out of range"));
        assert_eq!(issues[1].step_id, 2);
    }

    #[test]
    fn reports_structural_problems() {
        let text = GOOD.replace("id = 2", "id = 1");
        let p = parse_protocol(&text).unwrap();
        let issues = validate_steps(&p, &enforcer());
        assert!(
            issues
                .iter()
                .any(|i| i.message.contains("duplicate step id"))
        );
    }

    #[test]
    fn rejects_unknown_action_type() {
        let text = GOOD.replace("type = \"dispense\"", "type = \"centrifuge\"");
        assert!(parse_protocol(&text).is_err());
    }

    #[tokio::test]
    async fn shipped_odin_protocol_parses_and_flags_oversized_agar_dispense() {
        let store = ProtocolStore::new(package_protocols());
        let text = store.read_text("odin_crispr_rpsL").await.unwrap();
        let p = store.parse_named("odin_crispr_rpsL", &text).unwrap();
        assert_eq!(p.steps.len(), 15);
        let issues = validate_steps(&p, &enforcer());
        // Steps 1 and 2 pour 20 mL of agar in one dispense, above the 1 mL
        // single-dispense limit in safety_limits.toml.
        let ids: Vec<u32> = issues.iter().map(|i| i.step_id).collect();
        assert!(ids.contains(&1) && ids.contains(&2), "{issues:?}");
    }

    #[tokio::test]
    async fn load_missing_is_invalid_with_hint() {
        let dir = tempfile::tempdir().unwrap();
        let store = ProtocolStore::new(dir.path());
        match store.read_text("nope").await {
            Err(LabError::Invalid(msg)) => assert!(msg.contains("list_protocols")),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[tokio::test]
    async fn list_includes_custom_and_parse_errors() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("good.toml"), GOOD).unwrap();
        std::fs::write(dir.path().join("broken.toml"), "name = ").unwrap();
        std::fs::write(dir.path().join("notes.txt"), "ignored").unwrap();
        std::fs::create_dir(dir.path().join("custom")).unwrap();
        std::fs::write(dir.path().join("custom").join("mine.toml"), GOOD).unwrap();

        let store = ProtocolStore::new(dir.path());
        let list = store.list(&allowlist_for("good", GOOD)).await.unwrap();
        let ids: Vec<&str> = list.iter().map(|l| l.protocol_id.as_str()).collect();
        assert_eq!(ids, ["broken", "custom/mine", "good"]);
        assert!(list[0].error.is_some());
        assert_eq!(list[2].steps, Some(2));

        // A listing reports each file's hash and whether that content is
        // approved. `custom/mine` has identical content to `good` but is not
        // itself approved: approval is per id, not per hash.
        assert!(list[2].approved);
        assert_eq!(list[2].approved_by.as_deref(), Some("test operator"));
        assert_eq!(list[2].sha256.as_deref(), Some(content_hash(GOOD).as_str()));
        assert!(!list[1].approved);
        assert!(list[1].approved_by.is_none());
        // Unreadable content still gets an entry, with no hash.
        assert!(list[0].sha256.is_some());

        let text = store.read_text("custom/mine").await.unwrap();
        let loaded = store.parse_named("custom/mine", &text).unwrap();
        assert_eq!(loaded.name, "good");
    }

    #[tokio::test]
    async fn shipped_manifest_approves_nothing_until_a_lab_signs_off() {
        // Approval is local to the operating lab, so the shipped manifest
        // must parse but approve nothing, and the shipped Odin protocol must
        // be refused out of the box.
        let store = ProtocolStore::new(package_protocols());
        let text = store.read_text("odin_crispr_rpsL").await.unwrap();
        let allowlist = ProtocolAllowlist::load(package_manifest());
        assert!(
            allowlist.is_available(),
            "shipped manifest must parse: {:?}",
            allowlist.unavailable_reason()
        );
        assert!(allowlist.check("odin_crispr_rpsL", &text).is_err());

        // The commented template carries the shipped protocol's hash; if the
        // protocol is edited, the template must be updated with it.
        let manifest_text = std::fs::read_to_string(package_manifest()).unwrap();
        assert!(
            manifest_text.contains(&content_hash(&text)),
            "manifest template hash is stale for the shipped Odin protocol"
        );
    }

    #[tokio::test]
    async fn listing_marks_everything_unapproved_without_a_manifest() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("good.toml"), GOOD).unwrap();
        let store = ProtocolStore::new(dir.path());
        let list = store.list(&deny_all()).await.unwrap();
        assert_eq!(list.len(), 1);
        assert!(!list[0].approved);
        assert!(list[0].sha256.is_some());
    }

    #[tokio::test]
    async fn oversized_file_rejected() {
        let dir = tempfile::tempdir().unwrap();
        let big = "#".repeat(MAX_PROTOCOL_BYTES as usize + 1);
        std::fs::write(dir.path().join("big.toml"), big).unwrap();
        let store = ProtocolStore::new(dir.path());
        assert!(matches!(
            store.read_text("big").await,
            Err(LabError::Invalid(_))
        ));
    }
}
