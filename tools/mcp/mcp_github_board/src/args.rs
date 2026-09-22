//! Typed, validated tool arguments.
//!
//! Every tool deserializes its JSON arguments into one of the structs in
//! [`crate::specs`] using the types defined here. Deserialization never
//! panics: missing or malformed input becomes an
//! [`MCPError::InvalidParameters`] with a message naming the offending field.
//!
//! Values end up as arguments of the `board-manager` CLI. String values are
//! always passed in `--flag=value` form, so a value that starts with `-`
//! can never be interpreted as another flag, and the validators below reject
//! control characters and oversized input before a process is spawned.

use mcp_core::MCPError;
use serde::de::{self, DeserializeOwned, Deserializer, SeqAccess, Visitor};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::fmt;

/// Largest issue number accepted. GitHub's GraphQL `Int` is a signed 32-bit
/// integer, so larger numbers can never refer to a real issue.
pub const MAX_ISSUE_NUMBER: u64 = i32::MAX as u64;

/// Maximum length of an agent name.
pub const MAX_AGENT_NAME_LEN: usize = 64;

/// Maximum length of a claim session identifier.
pub const MAX_SESSION_ID_LEN: usize = 128;

/// Maximum length of a single label.
pub const MAX_LABEL_LEN: usize = 100;

/// Maximum number of labels in one filter list.
pub const MAX_LABELS: usize = 50;

/// Upper bound for `query_ready_work.limit`.
pub const MAX_READY_LIMIT: u64 = 100;

/// Upper bound for the stale-claim threshold (one year, in hours).
pub const MAX_THRESHOLD_HOURS: f64 = 24.0 * 365.0;

/// Deserialize tool arguments into `T`, mapping any error to
/// [`MCPError::InvalidParameters`].
///
/// A JSON `null` (some clients send it for "no arguments") is treated as an
/// empty object. Unknown fields are ignored for forward compatibility.
pub fn parse<T: DeserializeOwned>(args: Value) -> Result<T, MCPError> {
    let args = if args.is_null() { json!({}) } else { args };
    if !args.is_object() {
        return Err(MCPError::InvalidParameters(
            "tool arguments must be a JSON object".to_string(),
        ));
    }
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

// ============================================================================
// Issue numbers
// ============================================================================

/// A GitHub issue number (`1..=2^31-1`).
///
/// Accepts a JSON integer, an integral float (`42.0`) or a numeric string
/// with an optional `#` prefix (`"42"`, `"#42"`), because LLM clients are not
/// always strict about JSON types.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct IssueNumber(pub u64);

impl IssueNumber {
    fn checked(n: u64) -> Result<Self, String> {
        if n == 0 {
            Err("issue number must be >= 1".to_string())
        } else if n > MAX_ISSUE_NUMBER {
            Err(format!("issue number must be <= {MAX_ISSUE_NUMBER}"))
        } else {
            Ok(Self(n))
        }
    }

    /// The number as a CLI argument.
    pub fn arg(self) -> String {
        self.0.to_string()
    }
}

impl fmt::Display for IssueNumber {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "#{}", self.0)
    }
}

impl<'de> Deserialize<'de> for IssueNumber {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl Visitor<'_> for V {
            type Value = IssueNumber;

            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("a positive issue number such as 42 or \"#42\"")
            }

            fn visit_u64<E: de::Error>(self, v: u64) -> Result<Self::Value, E> {
                IssueNumber::checked(v).map_err(E::custom)
            }

            fn visit_i64<E: de::Error>(self, v: i64) -> Result<Self::Value, E> {
                u64::try_from(v)
                    .map_err(|_| E::custom("issue number must be >= 1"))
                    .and_then(|n| IssueNumber::checked(n).map_err(E::custom))
            }

            fn visit_f64<E: de::Error>(self, v: f64) -> Result<Self::Value, E> {
                if v.is_finite() && v.fract() == 0.0 && v >= 1.0 && v <= MAX_ISSUE_NUMBER as f64 {
                    Ok(IssueNumber(v as u64))
                } else {
                    Err(E::custom(format!("invalid issue number {v}")))
                }
            }

            fn visit_str<E: de::Error>(self, v: &str) -> Result<Self::Value, E> {
                let digits = v.trim().trim_start_matches('#');
                if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
                    return Err(E::custom(format!("invalid issue number '{v}'")));
                }
                let n: u64 = digits
                    .parse()
                    .map_err(|_| E::custom(format!("issue number '{v}' is too large")))?;
                IssueNumber::checked(n).map_err(E::custom)
            }
        }
        d.deserialize_any(V)
    }
}

// ============================================================================
// Free-text identifiers
// ============================================================================

/// Validate an identifier-like string (agent name, session id).
///
/// Trims surrounding whitespace and rejects empty values, control characters
/// and values longer than `max` characters.
pub fn check_text(field: &str, value: &str, max: usize) -> Result<String, MCPError> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(MCPError::InvalidParameters(format!(
            "'{field}' must not be empty"
        )));
    }
    if trimmed.chars().count() > max {
        return Err(MCPError::InvalidParameters(format!(
            "'{field}' must be at most {max} characters"
        )));
    }
    if trimmed.chars().any(char::is_control) {
        return Err(MCPError::InvalidParameters(format!(
            "'{field}' must not contain control characters"
        )));
    }
    Ok(trimmed.to_string())
}

/// Validate an agent name.
pub fn agent_name(value: &str) -> Result<String, MCPError> {
    check_text("agent_name", value, MAX_AGENT_NAME_LEN)
}

/// Validate an optional agent name; blank strings are treated as "not given".
pub fn opt_agent_name(value: Option<&str>) -> Result<Option<String>, MCPError> {
    match value {
        Some(v) if !v.trim().is_empty() => agent_name(v).map(Some),
        _ => Ok(None),
    }
}

/// Validate a claim session identifier.
pub fn session_id(value: &str) -> Result<String, MCPError> {
    check_text("session_id", value, MAX_SESSION_ID_LEN)
}

// ============================================================================
// Label lists
// ============================================================================

/// A list of labels, given either as a JSON array of strings or as a single
/// comma-separated string. Blank entries are dropped.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct LabelList(pub Vec<String>);

impl LabelList {
    /// Validate and return the labels joined with commas (the form
    /// `board-manager` expects), or `None` when the list is empty.
    pub fn to_arg(&self, field: &str) -> Result<Option<String>, MCPError> {
        if self.0.is_empty() {
            return Ok(None);
        }
        if self.0.len() > MAX_LABELS {
            return Err(MCPError::InvalidParameters(format!(
                "'{field}' accepts at most {MAX_LABELS} labels"
            )));
        }
        let mut out = Vec::with_capacity(self.0.len());
        for label in &self.0 {
            let label = check_text(field, label, MAX_LABEL_LEN)?;
            out.push(label);
        }
        Ok(Some(out.join(",")))
    }
}

impl<'de> Deserialize<'de> for LabelList {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = LabelList;

            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("an array of label names or a comma-separated string")
            }

            fn visit_str<E: de::Error>(self, v: &str) -> Result<Self::Value, E> {
                Ok(LabelList(
                    v.split(',')
                        .map(str::trim)
                        .filter(|s| !s.is_empty())
                        .map(String::from)
                        .collect(),
                ))
            }

            fn visit_unit<E: de::Error>(self) -> Result<Self::Value, E> {
                Ok(LabelList::default())
            }

            fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Self::Value, A::Error> {
                let mut out = Vec::new();
                while let Some(item) = seq.next_element::<String>()? {
                    let item = item.trim();
                    if item.contains(',') {
                        return Err(de::Error::custom(format!(
                            "label '{item}' contains a comma, which board-manager cannot express"
                        )));
                    }
                    if !item.is_empty() {
                        out.push(item.to_string());
                    }
                }
                Ok(LabelList(out))
            }
        }
        d.deserialize_any(V)
    }
}

// ============================================================================
// Board enums
// ============================================================================

/// Normalize an enum token like `board-manager` does: lowercase with spaces,
/// underscores and hyphens removed (`"in_progress"` == `"In Progress"`).
fn normalize(s: &str) -> String {
    s.chars()
        .filter(|c| !matches!(c, ' ' | '_' | '-'))
        .flat_map(char::to_lowercase)
        .collect()
}

/// Define a fieldless enum whose canonical strings match the `board-manager`
/// option names, with lenient (case/separator-insensitive) deserialization.
macro_rules! lenient_enum {
    ($(#[$meta:meta])* $name:ident, $what:literal, { $($variant:ident => $text:literal),+ $(,)? }) => {
        $(#[$meta])*
        #[derive(Debug, Clone, Copy, PartialEq, Eq)]
        pub enum $name {
            $(#[doc = $text] $variant),+
        }

        impl $name {
            /// All variants in declaration order.
            pub const ALL: &'static [$name] = &[$($name::$variant),+];

            /// Canonical string, as understood by `board-manager`.
            pub fn as_str(self) -> &'static str {
                match self {
                    $($name::$variant => $text),+
                }
            }

            /// Canonical strings of all variants (for JSON schema `enum`s).
            pub fn names() -> Vec<&'static str> {
                Self::ALL.iter().map(|v| v.as_str()).collect()
            }
        }

        impl std::str::FromStr for $name {
            type Err = String;

            fn from_str(s: &str) -> Result<Self, String> {
                let wanted = normalize(s);
                Self::ALL
                    .iter()
                    .copied()
                    .find(|v| normalize(v.as_str()) == wanted)
                    .ok_or_else(|| {
                        format!(
                            "invalid {} '{}' (expected one of: {})",
                            $what,
                            s,
                            Self::names().join(", ")
                        )
                    })
            }
        }

        impl<'de> Deserialize<'de> for $name {
            fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
                let s = String::deserialize(d)?;
                s.parse().map_err(de::Error::custom)
            }
        }
    };
}

lenient_enum!(
    /// Board status.
    Status, "status", {
        Todo => "Todo",
        InProgress => "In Progress",
        Blocked => "Blocked",
        Done => "Done",
        Abandoned => "Abandoned",
    }
);

lenient_enum!(
    /// Reason for releasing a claim.
    ReleaseReason, "release reason", {
        Completed => "completed",
        PrCreated => "pr_created",
        Blocked => "blocked",
        Abandoned => "abandoned",
        Error => "error",
    }
);

lenient_enum!(
    /// Board priority.
    Priority, "priority", {
        Critical => "Critical",
        High => "High",
        Medium => "Medium",
        Low => "Low",
    }
);

lenient_enum!(
    /// Board issue type.
    IssueType, "type", {
        Feature => "Feature",
        Bug => "Bug",
        TechDebt => "Tech Debt",
        Documentation => "Documentation",
    }
);

lenient_enum!(
    /// Estimated size.
    Size, "size", {
        XS => "XS",
        S => "S",
        M => "M",
        L => "L",
        XL => "XL",
    }
);

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Debug, Deserialize)]
    struct One {
        n: IssueNumber,
    }

    fn issue(v: Value) -> Result<IssueNumber, MCPError> {
        parse::<One>(json!({ "n": v })).map(|o| o.n)
    }

    #[test]
    fn issue_number_accepts_lenient_forms() {
        assert_eq!(issue(json!(42)).unwrap(), IssueNumber(42));
        assert_eq!(issue(json!(42.0)).unwrap(), IssueNumber(42));
        assert_eq!(issue(json!("42")).unwrap(), IssueNumber(42));
        assert_eq!(issue(json!(" #7 ")).unwrap(), IssueNumber(7));
        assert_eq!(
            issue(json!(MAX_ISSUE_NUMBER)).unwrap(),
            IssueNumber(MAX_ISSUE_NUMBER)
        );
    }

    #[test]
    fn issue_number_rejects_bad_values() {
        for bad in [
            json!(0),
            json!(-3),
            json!(1.5),
            json!("abc"),
            json!("#"),
            json!("-1"),
            json!("99999999999999999999999"),
            json!(MAX_ISSUE_NUMBER + 1),
            json!(true),
            json!(null),
            json!([1]),
        ] {
            let err = issue(bad.clone()).expect_err(&format!("{bad} should fail"));
            assert!(matches!(err, MCPError::InvalidParameters(_)), "{bad}");
        }
    }

    #[test]
    fn missing_field_is_invalid_parameters() {
        let err = parse::<One>(json!({})).unwrap_err();
        match err {
            MCPError::InvalidParameters(msg) => assert!(msg.contains("`n`"), "{msg}"),
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn parse_treats_null_as_empty_and_rejects_non_objects() {
        #[derive(Deserialize)]
        struct Empty {}
        assert!(parse::<Empty>(Value::Null).is_ok());
        assert!(parse::<Empty>(json!([1, 2])).is_err());
        assert!(parse::<Empty>(json!("x")).is_err());
    }

    #[test]
    fn text_validation() {
        assert_eq!(agent_name("  claude ").unwrap(), "claude");
        assert_eq!(agent_name("Claude Code").unwrap(), "Claude Code");
        assert!(agent_name("   ").is_err());
        assert!(agent_name("bad\nname").is_err());
        assert!(agent_name(&"x".repeat(MAX_AGENT_NAME_LEN + 1)).is_err());
        assert!(session_id(&"s".repeat(MAX_SESSION_ID_LEN)).is_ok());
        assert!(session_id(&"s".repeat(MAX_SESSION_ID_LEN + 1)).is_err());
        assert_eq!(opt_agent_name(None).unwrap(), None);
        assert_eq!(opt_agent_name(Some("  ")).unwrap(), None);
        assert_eq!(
            opt_agent_name(Some("crush")).unwrap(),
            Some("crush".to_string())
        );
    }

    #[test]
    fn enums_parse_leniently() {
        assert_eq!("in_progress".parse::<Status>().unwrap(), Status::InProgress);
        assert_eq!("IN-PROGRESS".parse::<Status>().unwrap(), Status::InProgress);
        assert_eq!("done".parse::<Status>().unwrap(), Status::Done);
        assert_eq!(
            "PR Created".parse::<ReleaseReason>().unwrap(),
            ReleaseReason::PrCreated
        );
        assert_eq!(
            "tech_debt".parse::<IssueType>().unwrap(),
            IssueType::TechDebt
        );
        assert_eq!("xl".parse::<Size>().unwrap(), Size::XL);
        let err = "later".parse::<Status>().unwrap_err();
        assert!(err.contains("expected one of: Todo, In Progress"), "{err}");
    }

    #[test]
    fn labels_accept_array_or_csv() {
        #[derive(Deserialize)]
        struct L {
            #[serde(default)]
            l: LabelList,
        }
        let p = |v: Value| parse::<L>(json!({ "l": v })).map(|x| x.l);
        assert_eq!(p(json!(["bug", " ui "])).unwrap().0, vec!["bug", "ui"]);
        assert_eq!(p(json!("bug, ui,,")).unwrap().0, vec!["bug", "ui"]);
        assert!(p(json!(null)).unwrap().0.is_empty());
        assert!(p(json!(["a,b"])).is_err());
        assert!(p(json!([1])).is_err());
        assert!(parse::<L>(json!({})).unwrap().l.0.is_empty());

        let list = LabelList(vec!["bug".into(), "help wanted".into()]);
        assert_eq!(
            list.to_arg("x").unwrap().as_deref(),
            Some("bug,help wanted")
        );
        assert_eq!(LabelList::default().to_arg("x").unwrap(), None);
        let too_many = LabelList(vec!["a".into(); MAX_LABELS + 1]);
        assert!(too_many.to_arg("x").is_err());
    }
}
