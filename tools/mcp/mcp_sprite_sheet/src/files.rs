//! Output-file helpers: filename sanitization and safe (atomic) writes.
//!
//! All generated files are written inside the configured output directory.
//! User-supplied filenames must be plain names (no directories, no `..`,
//! no absolute paths), which prevents path traversal out of that directory.

use std::path::{Path, PathBuf};

/// Maximum length of a generated or user-supplied filename.
const MAX_FILENAME_LEN: usize = 128;

/// Turn arbitrary text (project/sprite names) into a safe filename stem.
///
/// Keeps ASCII alphanumerics, `-`, `_` and `.`; everything else becomes `_`.
/// Leading dots are stripped so the result is never hidden or `..`.
pub fn safe_stem(s: &str) -> String {
    let mut out: String = s
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.' {
                c
            } else {
                '_'
            }
        })
        .collect();
    while out.starts_with('.') {
        out.remove(0);
    }
    out.truncate(MAX_FILENAME_LEN - 8);
    if out.is_empty() {
        "untitled".to_string()
    } else {
        out
    }
}

/// Validate a user-supplied output filename and ensure it has extension `ext`.
///
/// Rejects anything containing path separators, `..`, drive prefixes, or
/// control characters rather than silently rewriting it.
pub fn user_filename(name: &str, ext: &str) -> Result<String, String> {
    if name.chars().any(char::is_control) {
        return Err("filename must not contain control characters".into());
    }
    let name = name.trim();
    if name.is_empty() {
        return Err("filename must not be empty".into());
    }
    if name.contains(['/', '\\', ':']) || name.contains("..") {
        return Err(format!(
            "filename '{name}' must be a plain file name (no directories, '..', or drive \
             prefixes); files are always written to the server's output directory"
        ));
    }
    if name.starts_with('.') {
        return Err(format!("filename '{name}' must not start with '.'"));
    }
    let with_ext = if name.to_ascii_lowercase().ends_with(&format!(".{ext}")) {
        name.to_string()
    } else {
        format!("{name}.{ext}")
    };
    if with_ext.len() > MAX_FILENAME_LEN {
        return Err(format!(
            "filename is longer than {MAX_FILENAME_LEN} characters"
        ));
    }
    Ok(with_ext)
}

/// Resolve an optional user filename, falling back to a default stem.
pub fn output_name(user: Option<&str>, default_stem: &str, ext: &str) -> Result<String, String> {
    match user {
        Some(n) => user_filename(n, ext),
        None => Ok(format!("{}.{ext}", safe_stem(default_stem))),
    }
}

/// Write `bytes` to `dir/filename` atomically (temp file + rename).
pub async fn write_output(dir: &Path, filename: &str, bytes: Vec<u8>) -> Result<PathBuf, String> {
    tokio::fs::create_dir_all(dir)
        .await
        .map_err(|e| format!("Cannot create output directory {}: {e}", dir.display()))?;
    let path = dir.join(filename);
    let tmp = dir.join(format!(".{filename}.{}.tmp", uuid::Uuid::new_v4().simple()));
    tokio::fs::write(&tmp, &bytes)
        .await
        .map_err(|e| format!("Failed to write {}: {e}", tmp.display()))?;
    if let Err(e) = tokio::fs::rename(&tmp, &path).await {
        let _ = tokio::fs::remove_file(&tmp).await;
        return Err(format!("Failed to write {}: {e}", path.display()));
    }
    Ok(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_stem_strips_traversal() {
        assert_eq!(safe_stem("../../etc/passwd"), "_.._etc_passwd");
        assert_eq!(safe_stem("hero walk"), "hero_walk");
        assert_eq!(safe_stem("..."), "untitled");
        assert_eq!(safe_stem(""), "untitled");
    }

    #[test]
    fn user_filename_rejects_paths() {
        for bad in [
            "../x.png", "/etc/x", "a/b.png", "C:x.png", "a\\b", ".hidden", "", "x\n",
        ] {
            assert!(
                user_filename(bad, "png").is_err(),
                "{bad:?} should be rejected"
            );
        }
        assert_eq!(user_filename("sheet", "png").unwrap(), "sheet.png");
        assert_eq!(user_filename("sheet.PNG", "png").unwrap(), "sheet.PNG");
        assert_eq!(user_filename("sheet.v2", "json").unwrap(), "sheet.v2.json");
    }

    #[tokio::test]
    async fn write_output_creates_file() {
        let dir = std::env::temp_dir().join(format!("sprite-files-{}", uuid::Uuid::new_v4()));
        let p = write_output(&dir, "a.bin", vec![1, 2, 3]).await.unwrap();
        assert_eq!(tokio::fs::read(&p).await.unwrap(), vec![1, 2, 3]);
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }
}
