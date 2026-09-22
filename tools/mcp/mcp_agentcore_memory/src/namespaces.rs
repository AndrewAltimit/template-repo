//! Namespace catalogue and validation.
//!
//! Long-term memories live in hierarchical, `/`-separated namespaces such as
//! `codebase/patterns`. Each namespace maps to its own ChromaDB collection, so
//! a search only ever looks inside the exact namespace it names (there is no
//! implicit prefix search: `codebase` does not include `codebase/patterns`).

use serde_json::{Map, Value, json};

/// Predefined namespaces, grouped by category: `(category, key, namespace)`.
///
/// Any other namespace that passes [`validate_namespace`] may also be used;
/// these exist so that different agents converge on the same names.
pub const PREDEFINED: &[(&str, &str, &str)] = &[
    ("codebase", "architecture", "codebase/architecture"),
    ("codebase", "patterns", "codebase/patterns"),
    ("codebase", "conventions", "codebase/conventions"),
    ("codebase", "dependencies", "codebase/dependencies"),
    ("reviews", "pr", "reviews/pr"),
    ("reviews", "issues", "reviews/issues"),
    ("preferences", "user", "preferences/user"),
    ("preferences", "project", "preferences/project"),
    ("agents", "claude", "agents/claude"),
    ("agents", "gemini", "agents/gemini"),
    ("agents", "opencode", "agents/opencode"),
    ("agents", "crush", "agents/crush"),
    ("agents", "codex", "agents/codex"),
    (
        "personality",
        "voice_preferences",
        "personality/voice_preferences",
    ),
    (
        "personality",
        "expression_patterns",
        "personality/expression_patterns",
    ),
    (
        "personality",
        "reaction_history",
        "personality/reaction_history",
    ),
    (
        "personality",
        "avatar_settings",
        "personality/avatar_settings",
    ),
    ("context", "conversation_tone", "context/conversation_tone"),
    ("context", "user_preferences", "context/user_preferences"),
    (
        "context",
        "interaction_history",
        "context/interaction_history",
    ),
    ("cross_cutting", "security_patterns", "security/patterns"),
    ("cross_cutting", "testing_patterns", "testing/patterns"),
    (
        "cross_cutting",
        "performance_patterns",
        "performance/patterns",
    ),
];

/// Maximum namespace length in bytes.
pub const MAX_NAMESPACE_LEN: usize = 128;

/// The predefined namespaces as a nested `{category: {key: namespace}}` object
/// (the historical `list_namespaces` response shape).
pub fn predefined_tree() -> Value {
    let mut tree = Map::new();
    for (category, key, ns) in PREDEFINED {
        let entry = tree
            .entry(category.to_string())
            .or_insert_with(|| json!({}));
        if let Value::Object(m) = entry {
            m.insert(key.to_string(), json!(ns));
        }
    }
    Value::Object(tree)
}

/// Trim and validate a namespace, returning the canonical form.
///
/// Rules: 1-128 bytes; segments separated by single `/`; no leading/trailing
/// `/`; each segment made of ASCII letters, digits, `_`, `-` or `.` and not
/// `.`/`..`. The canonical form is what gets hashed into a collection name, so
/// `" codebase/patterns "` and `"codebase/patterns"` share one collection.
pub fn validate_namespace(raw: &str) -> Result<String, String> {
    let ns = raw.trim();
    if ns.is_empty() {
        return Err("namespace must not be empty".into());
    }
    if ns.len() > MAX_NAMESPACE_LEN {
        return Err(format!(
            "namespace is {} bytes; the maximum is {MAX_NAMESPACE_LEN}",
            ns.len()
        ));
    }
    for segment in ns.split('/') {
        if segment.is_empty() {
            return Err(format!(
                "namespace '{ns}' has an empty segment (no leading, trailing or doubled '/')"
            ));
        }
        if segment == "." || segment == ".." {
            return Err(format!("namespace '{ns}' contains a '.' or '..' segment"));
        }
        if let Some(bad) = segment
            .chars()
            .find(|c| !(c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.')))
        {
            return Err(format!(
                "namespace '{ns}' contains invalid character {bad:?} \
                 (allowed: letters, digits, '_', '-', '.', and '/' between segments)"
            ));
        }
    }
    Ok(ns.to_string())
}

/// True if `ns` is one of the [`PREDEFINED`] namespaces.
pub fn is_predefined(ns: &str) -> bool {
    PREDEFINED.iter().any(|(_, _, p)| *p == ns)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_predefined_are_valid_and_unique() {
        let mut seen = std::collections::HashSet::new();
        for (_, _, ns) in PREDEFINED {
            assert_eq!(validate_namespace(ns).as_deref(), Ok(*ns));
            assert!(seen.insert(*ns), "duplicate namespace {ns}");
        }
    }

    #[test]
    fn tree_shape_is_backward_compatible() {
        let t = predefined_tree();
        assert_eq!(t["codebase"]["patterns"], "codebase/patterns");
        assert_eq!(
            t["cross_cutting"]["performance_patterns"],
            "performance/patterns"
        );
        assert_eq!(t["agents"]["claude"], "agents/claude");
    }

    #[test]
    fn trims_whitespace() {
        assert_eq!(
            validate_namespace("  codebase/patterns ").unwrap(),
            "codebase/patterns"
        );
    }

    #[test]
    fn rejects_bad_namespaces() {
        for bad in [
            "",
            "   ",
            "/codebase",
            "codebase/",
            "a//b",
            "a/../b",
            "has space",
            "emoji\u{1F600}",
            "semi;colon",
        ] {
            assert!(validate_namespace(bad).is_err(), "should reject {bad:?}");
        }
        assert!(validate_namespace(&"a".repeat(MAX_NAMESPACE_LEN + 1)).is_err());
    }

    #[test]
    fn accepts_custom_namespaces() {
        for ok in ["projects/my-app", "a", "v1.2/notes", "team_x/sub-y/z"] {
            assert!(validate_namespace(ok).is_ok(), "should accept {ok:?}");
        }
    }

    #[test]
    fn predefined_lookup() {
        assert!(is_predefined("reviews/pr"));
        assert!(!is_predefined("reviews/other"));
    }
}
