//! Input validation for free-form string parameters.
//!
//! Numeric parameters are checked by `SafetyEnforcer`; this module covers the
//! string identifiers the enforcer never sees. Plate and image ids flow into
//! file names (the camera driver builds `<image_id>.png`), so they are held to
//! a strict filename-safe alphabet to rule out path traversal.

/// Maximum length of a plate / image / protocol identifier.
pub const MAX_ID_LEN: usize = 64;
/// Maximum length of a deck label (target, source, reagent).
pub const MAX_LABEL_LEN: usize = 128;
/// Maximum length of a human-action description.
pub const MAX_DESCRIPTION_LEN: usize = 2000;

fn is_id_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_' || c == '-'
}

fn is_label_char(c: char) -> bool {
    is_id_char(c) || matches!(c, ':' | '.' | ' ')
}

/// Validate a filename-safe identifier (plate ids, image ids, protocol ids).
///
/// Allowed: 1..=64 ASCII letters, digits, `_` and `-`.
pub fn identifier(field: &str, value: &str) -> Result<(), String> {
    if value.is_empty() {
        return Err(format!("{field} must not be empty"));
    }
    if value.len() > MAX_ID_LEN {
        return Err(format!(
            "{field} is {} characters; the maximum is {MAX_ID_LEN}",
            value.len()
        ));
    }
    if let Some(bad) = value.chars().find(|c| !is_id_char(*c)) {
        return Err(format!(
            "{field} contains invalid character {bad:?}; only ASCII letters, digits, '_' and '-' are allowed"
        ));
    }
    Ok(())
}

/// Validate a deck label such as `plate_1:A1` or `lb_broth`.
///
/// Allowed: 1..=128 ASCII letters, digits, `_`, `-`, `:`, `.` and spaces,
/// not starting or ending with a space.
pub fn label(field: &str, value: &str) -> Result<(), String> {
    if value.trim().is_empty() {
        return Err(format!("{field} must not be empty"));
    }
    if value.len() > MAX_LABEL_LEN {
        return Err(format!(
            "{field} is {} characters; the maximum is {MAX_LABEL_LEN}",
            value.len()
        ));
    }
    if value.trim() != value {
        return Err(format!("{field} must not start or end with whitespace"));
    }
    if let Some(bad) = value.chars().find(|c| !is_label_char(*c)) {
        return Err(format!(
            "{field} contains invalid character {bad:?}; allowed: ASCII letters, digits, '_', '-', ':', '.' and spaces"
        ));
    }
    Ok(())
}

/// Validate free text shown to a human operator (no control characters other
/// than newlines and tabs, bounded length).
pub fn description(field: &str, value: &str) -> Result<(), String> {
    if value.trim().is_empty() {
        return Err(format!("{field} must not be empty"));
    }
    if value.chars().count() > MAX_DESCRIPTION_LEN {
        return Err(format!("{field} exceeds {MAX_DESCRIPTION_LEN} characters"));
    }
    if value
        .chars()
        .any(|c| c.is_control() && c != '\n' && c != '\t')
    {
        return Err(format!("{field} must not contain control characters"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identifiers() {
        assert!(identifier("plate_id", "plate_1").is_ok());
        assert!(identifier("plate_id", "plate-selective_2").is_ok());
        assert!(identifier("plate_id", "").is_err());
        assert!(identifier("plate_id", "../etc/passwd").is_err());
        assert!(identifier("plate_id", "a/b").is_err());
        assert!(identifier("plate_id", "a\\b").is_err());
        assert!(identifier("plate_id", "plate 1").is_err());
        assert!(identifier("plate_id", &"a".repeat(MAX_ID_LEN + 1)).is_err());
        assert!(identifier("plate_id", &"a".repeat(MAX_ID_LEN)).is_ok());
    }

    #[test]
    fn labels() {
        assert!(label("target", "plate_1:A1").is_ok());
        assert!(label("target", "tube 2.5").is_ok());
        assert!(label("target", " ").is_err());
        assert!(label("target", " padded").is_err());
        assert!(label("target", "semi;colon").is_err());
        assert!(label("target", "new\nline").is_err());
    }

    #[test]
    fn descriptions() {
        assert!(description("description", "Place plates\non the deck").is_ok());
        assert!(description("description", "").is_err());
        assert!(description("description", "bell\u{7}").is_err());
        assert!(description("description", &"x".repeat(MAX_DESCRIPTION_LEN + 1)).is_err());
    }
}
