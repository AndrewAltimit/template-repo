//! Validate and sanitize all content of a gh invocation.
//!
//! For every content slot found by [`crate::args`]:
//!
//! | Check | Inline text | Content files |
//! |-------|-------------|---------------|
//! | secrets masked | yes (all arguments) | yes |
//! | Unicode emoji rejected | yes (all arguments) | yes |
//! | escaped emoji (`\uD83D...`) rejected | `gh api` fields | `gh api` files |
//! | reaction image must use a file | `--body`, api `body=` | - |
//! | reaction image URLs verified | - | markdown files |
//! | @mentions neutralized | markdown text | markdown files |
//!
//! Content files are read **once**, sanitized, and written to a private
//! temporary file that replaces the original path in the arguments. gh
//! therefore posts exactly the bytes that were validated: swapping the file
//! after validation (or naming a file that does not exist yet) cannot
//! smuggle content past the checks, and the user's file is never modified.

use crate::args::{self, Parsed, Slot, SlotKind};
use crate::config::Config;
use crate::error::{Error, Result};
use crate::policy;
use crate::validation::{SecretMasker, UrlValidator, comments};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};

/// Largest content file accepted (GitHub bodies are far smaller; API inputs
/// such as blob uploads can be larger).
pub const MAX_CONTENT_FILE_BYTES: u64 = 25 * 1024 * 1024;

/// Validation settings for one invocation.
pub struct Validators<'a> {
    pub masker: &'a SecretMasker,
    pub urls: &'a UrlValidator,
    pub allowed_mentions: Vec<String>,
    /// `--gh-validator-strip-invalid-images`: drop bad images instead of failing.
    pub strip_invalid_images: bool,
}

impl<'a> Validators<'a> {
    pub fn new(
        config: &Config,
        masker: &'a SecretMasker,
        urls: &'a UrlValidator,
        strip: bool,
    ) -> Self {
        Self {
            masker,
            urls,
            allowed_mentions: config.allowed_mentions(),
            strip_invalid_images: strip,
        }
    }
}

/// Result of sanitizing an invocation.
#[derive(Debug)]
pub enum Outcome {
    /// Run gh with these arguments; keep `temp_files` alive until it exits.
    Run {
        args: Vec<String>,
        temp_files: TempFiles,
        notices: Vec<String>,
    },
    /// Nothing left to post (all images stripped from an image-only body).
    Skip { notice: String },
}

/// Sanitize `args` (already alias-expanded).
pub fn sanitize(args: &[String], v: &Validators<'_>) -> Result<Outcome> {
    let mut notices = Vec::new();

    let (mut args, masked) = v.masker.mask_args(args);
    if masked {
        notices.push("Secrets were masked in command arguments".to_string());
    }
    // Re-parse: masking can change argument lengths.
    let parsed = args::parse(&args);

    if let Some(c) = comments::find_emoji_in_args(&args) {
        return Err(Error::emoji(c, "command arguments"));
    }

    let mut temp_files = TempFiles::default();
    for slot in &parsed.slots {
        if slot.kind.is_file() {
            let path = slot.value(&args).to_string();
            match sanitize_file(&path, slot, v, &mut notices)? {
                Some(content) => {
                    let temp = temp_files.create(&content)?;
                    slot.set_value(&mut args, &temp.to_string_lossy());
                },
                None => {
                    return Ok(Outcome::Skip {
                        notice: format!(
                            "Content of {path} is empty after stripping invalid images, \
                             skipping command"
                        ),
                    });
                },
            }
        } else {
            let text = slot.value(&args).to_string();
            let new = sanitize_text(&text, slot, v, &mut notices)?;
            if new != text {
                slot.set_value(&mut args, &new);
            }
        }
    }

    if policy::is_gist_create(&parsed) {
        check_gist_files(&parsed, v.masker)?;
    }

    Ok(Outcome::Run {
        args,
        temp_files,
        notices,
    })
}

fn is_body(slot: &Slot) -> bool {
    match slot.kind {
        SlotKind::Body => true,
        SlotKind::ApiField => slot.field.as_deref() == Some("body"),
        _ => false,
    }
}

fn sanitize_text(
    text: &str,
    slot: &Slot,
    v: &Validators<'_>,
    notices: &mut Vec<String>,
) -> Result<String> {
    if is_body(slot) && comments::has_reaction_image(text) {
        return Err(Error::FormattingViolation {
            description: format!(
                "reaction image passed inline with {} (use --body-file instead)",
                slot.flag
            ),
        });
    }
    if slot.kind == SlotKind::ApiField
        && let Some(c) = comments::find_escaped_emoji(text)
    {
        return Err(Error::emoji(c, format!("escaped in {}", slot.flag)));
    }
    Ok(neutralize(text, slot, v, notices, &slot.flag))
}

/// Read, validate, and sanitize a content file. `Ok(None)` means the
/// content became empty after stripping images (skip the command).
fn sanitize_file(
    path: &str,
    slot: &Slot,
    v: &Validators<'_>,
    notices: &mut Vec<String>,
) -> Result<Option<String>> {
    let content = read_content_file(path)?;

    if let Some(c) = comments::find_emoji(&content) {
        return Err(Error::emoji(c, path));
    }
    if matches!(slot.kind, SlotKind::ApiInput | SlotKind::ApiFieldFile)
        && let Some(c) = comments::find_escaped_emoji(&content)
    {
        return Err(Error::emoji(c, format!("{path} (escaped)")));
    }

    let (mut content, masked) = v.masker.mask(&content);
    if masked {
        notices.push(format!("Secrets were masked in {path}"));
    }

    if slot.is_markdown() {
        let urls = UrlValidator::extract_reaction_urls(&content);
        if !urls.is_empty() {
            if v.strip_invalid_images {
                let (stripped, removed) = v.urls.strip_invalid_images(&content);
                if !removed.is_empty() {
                    for (url, reason) in &removed {
                        notices.push(format!("WARNING: Stripped invalid image: {url} ({reason})"));
                    }
                    if stripped.trim().is_empty() {
                        return Ok(None);
                    }
                    content = stripped;
                }
            } else {
                for url in urls {
                    v.urls.validate_exists(&url)?;
                }
            }
        }
    }

    Ok(Some(neutralize(&content, slot, v, notices, path)))
}

fn neutralize(
    text: &str,
    slot: &Slot,
    v: &Validators<'_>,
    notices: &mut Vec<String>,
    location: &str,
) -> String {
    if !slot.is_markdown() {
        return text.to_string();
    }
    let (out, found) = comments::neutralize_mentions(text, &v.allowed_mentions);
    if !found.is_empty() {
        notices.push(format!(
            "Neutralized @mentions in {location}: {}",
            found.join(", ")
        ));
    }
    out
}

/// Files attached by `gh gist create` must not contain secrets (they are
/// uploaded verbatim, so they are rejected rather than rewritten).
fn check_gist_files(parsed: &Parsed, masker: &SecretMasker) -> Result<()> {
    for (_, path) in parsed.operands() {
        let content = read_content_file(path)?;
        if masker.contains_secret(&content) {
            return Err(Error::Blocked {
                reason: format!("{path} contains a secret; refusing to upload it as a gist"),
                help: Some("Remove the secret from the file first."),
            });
        }
    }
    Ok(())
}

/// Read a UTF-8 content file (fail-closed: missing, oversized, non-UTF-8,
/// or non-regular files are errors).
fn read_content_file(path: &str) -> Result<String> {
    let err = |reason: String| Error::ContentFile {
        path: path.to_string(),
        reason,
    };
    let meta = std::fs::metadata(path).map_err(|e| err(format!("cannot read: {e}")))?;
    if !meta.is_file() {
        return Err(err("not a regular file".to_string()));
    }
    if meta.len() > MAX_CONTENT_FILE_BYTES {
        return Err(err(format!("larger than {MAX_CONTENT_FILE_BYTES} bytes")));
    }
    let bytes = std::fs::read(path).map_err(|e| err(format!("cannot read: {e}")))?;
    String::from_utf8(bytes).map_err(|_| err("not valid UTF-8".to_string()))
}

/// Private temporary files, deleted on drop.
#[derive(Debug, Default)]
pub struct TempFiles {
    paths: Vec<PathBuf>,
}

static TEMP_COUNTER: AtomicU32 = AtomicU32::new(0);

impl TempFiles {
    pub fn is_empty(&self) -> bool {
        self.paths.is_empty()
    }

    /// Write `content` to a new private (0600) file in the temp directory.
    pub fn create(&mut self, content: &str) -> Result<PathBuf> {
        let dir = std::env::temp_dir();
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.subsec_nanos())
            .unwrap_or_default();
        for _ in 0..16 {
            let n = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
            let path = dir.join(format!(
                "gh-validator-{}-{nanos:09}-{n}.md",
                std::process::id()
            ));
            match open_new_private(&path) {
                Ok(mut file) => {
                    self.paths.push(path.clone());
                    file.write_all(content.as_bytes())
                        .and_then(|()| file.flush())
                        .map_err(|e| temp_err(&path, e))?;
                    return Ok(path);
                },
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(e) => return Err(temp_err(&path, e)),
            }
        }
        Err(Error::ContentFile {
            path: dir.display().to_string(),
            reason: "could not create a unique temporary file".to_string(),
        })
    }
}

fn temp_err(path: &Path, e: std::io::Error) -> Error {
    Error::ContentFile {
        path: path.display().to_string(),
        reason: format!("cannot write sanitized copy: {e}"),
    }
}

fn open_new_private(path: &Path) -> std::io::Result<std::fs::File> {
    let mut opts = std::fs::OpenOptions::new();
    opts.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        opts.mode(0o600);
    }
    opts.open(path)
}

impl Drop for TempFiles {
    fn drop(&mut self) {
        for path in &self.paths {
            let _ = std::fs::remove_file(path);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg() -> Config {
        let mut c = Config::default();
        c.settings.log_masked_secrets = false;
        c
    }

    fn a(s: &[&str]) -> Vec<String> {
        s.iter().map(|x| x.to_string()).collect()
    }

    fn run(args: &[String], env: &[(&str, &str)]) -> Result<Outcome> {
        let config = cfg();
        let masker = SecretMasker::from_env(
            &config,
            env.iter().map(|(k, v)| (k.to_string(), v.to_string())),
        );
        let urls = UrlValidator::new(1, 1);
        let v = Validators::new(&config, &masker, &urls, false);
        sanitize(args, &v)
    }

    fn run_args(outcome: Outcome) -> (Vec<String>, TempFiles) {
        match outcome {
            Outcome::Run {
                args, temp_files, ..
            } => (args, temp_files),
            Outcome::Skip { .. } => panic!("unexpected skip"),
        }
    }

    #[test]
    fn inline_secrets_masked_and_mentions_neutralized() {
        let (args, _) = run_args(
            run(
                &a(&[
                    "pr",
                    "comment",
                    "1",
                    "--body",
                    "hi @octocat token=gho_abcdef",
                ]),
                &[("GH_TOKEN", "gho_abcdef")],
            )
            .unwrap(),
        );
        assert_eq!(args[4], "hi `@octocat` token=[MASKED_GH_TOKEN]");
    }

    #[test]
    fn api_fields_are_validated() {
        let (args, _) = run_args(
            run(
                &a(&[
                    "api",
                    "repos/o/r/issues/1/comments",
                    "-f",
                    "body=ping @hubot",
                ]),
                &[],
            )
            .unwrap(),
        );
        assert_eq!(args[3], "body=ping `@hubot`");

        let err = run(&a(&["api", "x", "-f", "body=hi \u{1F600}"]), &[]).unwrap_err();
        assert!(matches!(err, Error::UnicodeEmoji { .. }));

        let err = run(
            &a(&["api", "graphql", "-f", r"query=mutation{x(body:\u{1F600})}"]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::UnicodeEmoji { .. }));

        let err = run(
            &a(&[
                "api",
                "x",
                "-f",
                "body=![Reaction](https://x/reaction/a.png)",
            ]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::FormattingViolation { .. }));

        // Non-text api fields are not rewritten.
        let (args, _) = run_args(run(&a(&["api", "x", "-f", "q=author:@me"]), &[]).unwrap());
        assert_eq!(args[3], "q=author:@me");
    }

    #[test]
    fn inline_reaction_images_rejected() {
        for args in [
            &[
                "pr",
                "comment",
                "1",
                "--body",
                "![Reaction](https://x/reaction/a.png)",
            ][..],
            &[
                "pr",
                "comment",
                "1",
                "-b![Reaction](https://x/reaction/a.png)",
            ],
            &[
                "issue",
                "comment",
                "1",
                "--body=\\![Reaction](https://x/y.png)",
            ],
        ] {
            assert!(
                matches!(run(&a(args), &[]), Err(Error::FormattingViolation { .. })),
                "{args:?}"
            );
        }
    }

    #[test]
    fn emoji_anywhere_in_args_rejected() {
        let err = run(
            &a(&["pr", "create", "--title", "\u{1F680} Launch", "-b", "x"]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::UnicodeEmoji { .. }));
    }

    #[test]
    fn body_file_is_copied_sanitized_and_original_untouched() {
        let dir = tempfile::tempdir().unwrap();
        let body = dir.path().join("body.md");
        std::fs::write(&body, "Secret: s3cr3t-value\ncc @octocat\n").unwrap();
        let body_str = body.to_string_lossy().to_string();

        let (args, temps) = run_args(
            run(
                &a(&["pr", "comment", "1", "--body-file", &body_str]),
                &[("GH_TOKEN", "s3cr3t-value")],
            )
            .unwrap(),
        );
        // Original file unchanged.
        assert_eq!(
            std::fs::read_to_string(&body).unwrap(),
            "Secret: s3cr3t-value\ncc @octocat\n"
        );
        // gh gets a sanitized private copy.
        assert_ne!(args[4], body_str);
        let copy = std::fs::read_to_string(&args[4]).unwrap();
        assert_eq!(copy, "Secret: [MASKED_GH_TOKEN]\ncc `@octocat`\n");
        drop(temps);
        assert!(!Path::new(&args[4]).exists(), "temp file cleaned up");
    }

    #[test]
    fn auto_detected_secret_in_file_masked() {
        let dir = tempfile::tempdir().unwrap();
        let body = dir.path().join("b.md");
        let token = format!("ghp_{}", "x".repeat(36));
        std::fs::write(&body, format!("leak {token}")).unwrap();
        let (args, _t) = run_args(
            run(
                &a(&["pr", "comment", "1", "-F", &body.to_string_lossy()]),
                &[],
            )
            .unwrap(),
        );
        let copy = std::fs::read_to_string(&args[4]).unwrap();
        assert_eq!(copy, "leak [MASKED_GITHUB_TOKEN]");
    }

    #[test]
    fn file_emoji_rejected() {
        let dir = tempfile::tempdir().unwrap();
        let body = dir.path().join("b.md");
        std::fs::write(&body, "\u{1F916} Generated with Claude Code").unwrap();
        let err = run(
            &a(&["pr", "create", "-t", "x", "-F", &body.to_string_lossy()]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::UnicodeEmoji { .. }));
    }

    #[test]
    fn api_input_escaped_emoji_rejected() {
        let dir = tempfile::tempdir().unwrap();
        let input = dir.path().join("in.json");
        std::fs::write(&input, r#"{"body":"hi \ud83d\ude00"}"#).unwrap();
        let err = run(
            &a(&[
                "api",
                "repos/o/r/issues/1/comments",
                "--input",
                &input.to_string_lossy(),
            ]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::UnicodeEmoji { .. }));
    }

    #[test]
    fn api_field_file_is_sanitized() {
        let dir = tempfile::tempdir().unwrap();
        let f = dir.path().join("b.md");
        std::fs::write(&f, "hello @octocat").unwrap();
        let (args, _t) = run_args(
            run(
                &a(&["api", "x", "-F", &format!("body=@{}", f.to_string_lossy())]),
                &[],
            )
            .unwrap(),
        );
        let path = args[3].strip_prefix("body=@").unwrap();
        assert_eq!(std::fs::read_to_string(path).unwrap(), "hello `@octocat`");
    }

    #[test]
    fn missing_or_bad_files_fail_closed() {
        // A file that does not exist yet could be created after validation.
        let err = run(
            &a(&["pr", "comment", "1", "--body-file", "/nonexistent/x.md"]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::ContentFile { .. }));

        let dir = tempfile::tempdir().unwrap();
        let err = run(
            &a(&[
                "pr",
                "comment",
                "1",
                "--body-file",
                &dir.path().to_string_lossy(),
            ]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::ContentFile { .. }));

        let bin = dir.path().join("bin");
        std::fs::write(&bin, [0xff, 0xfe, 0x00]).unwrap();
        let err = run(
            &a(&["pr", "comment", "1", "-F", &bin.to_string_lossy()]),
            &[],
        )
        .unwrap_err();
        assert!(matches!(err, Error::ContentFile { .. }));
    }

    #[test]
    fn gist_with_secret_rejected() {
        let dir = tempfile::tempdir().unwrap();
        let f = dir.path().join(".env");
        std::fs::write(&f, format!("TOKEN=ghp_{}", "y".repeat(36))).unwrap();
        let err = run(&a(&["gist", "create", &f.to_string_lossy()]), &[]).unwrap_err();
        assert!(matches!(err, Error::Blocked { .. }));

        std::fs::write(&f, "harmless").unwrap();
        assert!(run(&a(&["gist", "create", &f.to_string_lossy()]), &[]).is_ok());
    }

    #[test]
    fn strip_mode_skips_image_only_body() {
        let dir = tempfile::tempdir().unwrap();
        let f = dir.path().join("b.md");
        std::fs::write(&f, "![Reaction](https://evil.example.com/reaction/x.png)\n").unwrap();
        let config = cfg();
        let masker = SecretMasker::from_env(&config, Vec::new());
        let urls = UrlValidator::new(1, 1);
        let v = Validators::new(&config, &masker, &urls, true);
        let out = sanitize(&a(&["pr", "comment", "1", "-F", &f.to_string_lossy()]), &v).unwrap();
        assert!(matches!(out, Outcome::Skip { .. }));
    }

    #[test]
    fn temp_files_are_private() {
        let mut t = TempFiles::default();
        let p = t.create("x").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = std::fs::metadata(&p).unwrap().permissions().mode();
            assert_eq!(mode & 0o077, 0);
        }
        assert_eq!(std::fs::read_to_string(&p).unwrap(), "x");
        drop(t);
        assert!(!p.exists());
    }
}
