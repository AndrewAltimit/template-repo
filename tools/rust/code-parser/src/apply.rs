//! Applying extracted changes to a directory tree (`fs` feature).
//!
//! Every path goes through [`crate::path::sanitize`] and is then resolved against the
//! canonical base directory; existing symlinks along the way must point back inside
//! the base. Files are written atomically (temp file + rename) so an interrupted run
//! never leaves a half-written file, and existing permissions are preserved.
//!
//! A time-of-check/time-of-use race with a concurrent process swapping directories
//! for symlinks is out of scope; do not point this at a directory an attacker can
//! write to concurrently.

use std::collections::HashMap;
use std::fmt;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use tracing::{debug, warn};

use crate::block::CodeBlock;
use crate::diff::{self, FilePatch};
use crate::edit::{self, EditInstruction};
use crate::error::{CodeParserError, Result};
use crate::path::sanitize;

/// Options controlling how changes are applied.
#[derive(Debug, Clone, Copy, Default)]
pub struct ApplyOptions {
    /// Compute and report results without touching the file system.
    pub dry_run: bool,
    /// Also write code blocks whose closing fence is missing. Off by default because
    /// an unterminated block usually means the response was truncated.
    pub allow_unterminated: bool,
}

/// Outcome for one file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApplyStatus {
    /// The file did not exist and was created.
    Created,
    /// The file existed and its content changed.
    Modified,
    /// The file already had exactly this content.
    Unchanged,
    /// The file was deleted (patch against `/dev/null`, or the old side of a rename).
    Deleted,
    /// The change was deliberately not applied; the string says why.
    Skipped(String),
    /// The change failed; the string is the error message.
    Failed(String),
}

impl ApplyStatus {
    /// Whether this outcome is a failure.
    pub fn is_error(&self) -> bool {
        matches!(self, Self::Failed(_))
    }

    /// Whether the file system was (or in a dry run, would be) changed.
    pub fn is_change(&self) -> bool {
        matches!(self, Self::Created | Self::Modified | Self::Deleted)
    }
}

impl fmt::Display for ApplyStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Created => f.write_str("created"),
            Self::Modified => f.write_str("modified"),
            Self::Unchanged => f.write_str("unchanged"),
            Self::Deleted => f.write_str("deleted"),
            Self::Skipped(why) => write!(f, "skipped: {why}"),
            Self::Failed(err) => write!(f, "error: {err}"),
        }
    }
}

/// Outcome for one path, in application order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApplyEntry {
    /// Sanitized relative path, or the raw path if it failed sanitization.
    pub path: String,
    /// What happened.
    pub status: ApplyStatus,
}

/// Result of an apply run.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ApplyReport {
    /// One entry per attempted file operation, in order.
    pub entries: Vec<ApplyEntry>,
}

impl ApplyReport {
    /// Whether any operation failed.
    pub fn has_errors(&self) -> bool {
        self.entries.iter().any(|e| e.status.is_error())
    }

    /// Paths that were (or would be) created, modified, or deleted.
    pub fn changed_paths(&self) -> impl Iterator<Item = &str> {
        self.entries
            .iter()
            .filter(|e| e.status.is_change())
            .map(|e| e.path.as_str())
    }

    /// Legacy `path -> status string` map ("created", "modified", "error: ...").
    /// When a path appears more than once, the last outcome wins.
    pub fn to_status_map(&self) -> HashMap<String, String> {
        self.entries
            .iter()
            .map(|e| (e.path.clone(), e.status.to_string()))
            .collect()
    }
}

/// Apply code blocks (full-file writes; diff blocks are applied as patches).
pub(crate) fn apply_blocks(
    blocks: &[CodeBlock],
    base: &Path,
    opts: ApplyOptions,
) -> Result<ApplyReport> {
    let mut s = Session::open(base, opts)?;
    for block in blocks {
        s.block(block);
    }
    Ok(s.report)
}

/// Apply parsed unified-diff patches.
pub(crate) fn apply_patches(
    patches: &[FilePatch],
    base: &Path,
    opts: ApplyOptions,
) -> Result<ApplyReport> {
    let mut s = Session::open(base, opts)?;
    for patch in patches {
        s.patch(patch);
    }
    Ok(s.report)
}

/// Apply search/replace edit instructions.
pub(crate) fn apply_edits(
    edits: &[EditInstruction],
    base: &Path,
    opts: ApplyOptions,
) -> Result<ApplyReport> {
    let mut s = Session::open(base, opts)?;
    for e in edits {
        s.edit(e);
    }
    Ok(s.report)
}

struct Session {
    root: PathBuf,
    opts: ApplyOptions,
    /// Content written earlier in this run (`None` = deleted), so later operations
    /// see earlier ones even in a dry run.
    overlay: HashMap<PathBuf, Option<String>>,
    report: ApplyReport,
}

impl Session {
    fn open(base: &Path, opts: ApplyOptions) -> Result<Self> {
        if !opts.dry_run && !base.exists() {
            fs::create_dir_all(base)?;
        }
        let root = base.canonicalize()?;
        if !root.is_dir() {
            return Err(CodeParserError::Io(io::Error::new(
                io::ErrorKind::NotADirectory,
                format!("base path is not a directory: {}", root.display()),
            )));
        }
        Ok(Self {
            root,
            opts,
            overlay: HashMap::new(),
            report: ApplyReport::default(),
        })
    }

    fn record(&mut self, path: impl Into<String>, status: ApplyStatus) {
        let path = path.into();
        match &status {
            ApplyStatus::Failed(e) => warn!("{path}: {e}"),
            other => debug!("{path}: {other}"),
        }
        self.report.entries.push(ApplyEntry { path, status });
    }

    /// Sanitize `raw` and resolve it under the root, refusing symlink escapes.
    fn resolve(&self, raw: &str) -> Result<(String, PathBuf)> {
        let rel = sanitize(raw)?;
        let mut path = self.root.clone();
        for comp in rel.split('/') {
            path.push(comp);
            match fs::symlink_metadata(&path) {
                Ok(meta) if meta.file_type().is_symlink() => {
                    let target = fs::canonicalize(&path).map_err(|_| {
                        CodeParserError::PathTraversal(format!("{raw} (dangling symlink)"))
                    })?;
                    if !target.starts_with(&self.root) {
                        warn!("Symlink escapes base directory: {}", path.display());
                        return Err(CodeParserError::PathTraversal(raw.to_string()));
                    }
                },
                Ok(_) => {},
                Err(e) if e.kind() == io::ErrorKind::NotFound => break,
                Err(e) => return Err(e.into()),
            }
        }
        let full = self.root.join(&rel);
        Ok((rel, full))
    }

    fn read(&self, path: &Path) -> Result<Option<String>> {
        if let Some(v) = self.overlay.get(path) {
            return Ok(v.clone());
        }
        match fs::read_to_string(path) {
            Ok(s) => Ok(Some(s)),
            Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(e.into()),
        }
    }

    fn write(&mut self, path: &Path, content: String) -> Result<ApplyStatus> {
        let status = match self.read(path)? {
            Some(existing) if existing == content => return Ok(ApplyStatus::Unchanged),
            Some(_) => ApplyStatus::Modified,
            None => ApplyStatus::Created,
        };
        if !self.opts.dry_run {
            atomic_write(path, &content)?;
        }
        self.overlay.insert(path.to_path_buf(), Some(content));
        Ok(status)
    }

    fn delete(&mut self, path: &Path) -> Result<ApplyStatus> {
        if self.read(path)?.is_none() {
            return Ok(ApplyStatus::Failed("file does not exist".to_string()));
        }
        if !self.opts.dry_run {
            fs::remove_file(path)?;
        }
        self.overlay.insert(path.to_path_buf(), None);
        Ok(ApplyStatus::Deleted)
    }

    fn block(&mut self, block: &CodeBlock) {
        let is_diff = block.is_diff();
        let label = match (&block.filename, is_diff) {
            (Some(f), _) => f.clone(),
            (None, true) => format!("<diff block at line {}>", block.start_line),
            (None, false) => {
                debug!(
                    "Skipping code block without filename (line {})",
                    block.start_line
                );
                return;
            },
        };
        if !block.terminated && !self.opts.allow_unterminated {
            self.record(
                label,
                ApplyStatus::Skipped("unterminated code block (response may be truncated)".into()),
            );
            return;
        }
        if is_diff {
            match diff::parse(&block.content) {
                Ok(patches) => patches.iter().for_each(|p| self.patch(p)),
                Err(e) => self.record(label, ApplyStatus::Failed(e.to_string())),
            }
            return;
        }

        let result = self.resolve(&label).and_then(|(rel, path)| {
            let existing = self.read(&path)?;
            let mut content = block.content.clone();
            if !content.is_empty() && !content.ends_with('\n') {
                content.push('\n');
            }
            if existing.as_deref().is_some_and(|e| e.contains("\r\n")) {
                content = content.replace('\n', "\r\n");
            }
            Ok((rel, self.write(&path, content)?))
        });
        match result {
            Ok((rel, status)) => self.record(rel, status),
            Err(e) => self.record(label, ApplyStatus::Failed(e.to_string())),
        }
    }

    fn patch(&mut self, patch: &FilePatch) {
        let label = patch.path().unwrap_or("<unknown>").to_string();
        if let Err(e) = self.try_patch(patch) {
            self.record(label, ApplyStatus::Failed(e.to_string()));
        }
    }

    fn try_patch(&mut self, patch: &FilePatch) -> Result<()> {
        let source_raw = patch.old_path.as_deref().or(patch.new_path.as_deref());
        let (src_rel, src_path) = self.resolve(source_raw.unwrap_or_default())?;

        let original = if patch.is_new_file() {
            let (_, target) = self.resolve(patch.new_path.as_deref().unwrap_or_default())?;
            if self.read(&target)?.is_some_and(|c| !c.is_empty()) {
                return Err(CodeParserError::InvalidPatch(format!(
                    "{src_rel} already exists but the patch creates it"
                )));
            }
            String::new()
        } else {
            self.read(&src_path)?.ok_or_else(|| {
                CodeParserError::Io(io::Error::new(
                    io::ErrorKind::NotFound,
                    format!("{src_rel} does not exist"),
                ))
            })?
        };

        let updated = patch.apply(&original)?;

        if patch.is_deletion() {
            let status = self.delete(&src_path)?;
            self.record(src_rel, status);
            return Ok(());
        }
        let (dst_rel, dst_path) = self.resolve(patch.new_path.as_deref().unwrap_or_default())?;
        let status = self.write(&dst_path, updated)?;
        self.record(dst_rel, status);
        if patch.is_rename() {
            let status = self.delete(&src_path)?;
            self.record(src_rel, status);
        }
        Ok(())
    }

    fn edit(&mut self, e: &EditInstruction) {
        let result = self.resolve(&e.file).and_then(|(rel, path)| {
            let updated = match self.read(&path)? {
                Some(content) => edit::apply(&content, e)?,
                None if e.old.is_empty() => edit::apply("", e)?,
                None => {
                    return Err(CodeParserError::Io(io::Error::new(
                        io::ErrorKind::NotFound,
                        format!("{rel} does not exist"),
                    )));
                },
            };
            Ok((rel, self.write(&path, updated)?))
        });
        match result {
            Ok((rel, status)) => self.record(rel, status),
            Err(err) => self.record(e.file.clone(), ApplyStatus::Failed(err.to_string())),
        }
    }
}

/// Write `content` to `path` via a sibling temp file and rename.
fn atomic_write(path: &Path, content: &str) -> io::Result<()> {
    static COUNTER: AtomicU64 = AtomicU64::new(0);

    let parent = path
        .parent()
        .ok_or_else(|| io::Error::other("path has no parent directory"))?;
    fs::create_dir_all(parent)?;
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    let tmp = parent.join(format!(
        ".{name}.code-parser-{}-{}.tmp",
        std::process::id(),
        COUNTER.fetch_add(1, Ordering::Relaxed)
    ));
    let permissions = fs::metadata(path).ok().map(|m| m.permissions());

    let result = fs::write(&tmp, content)
        .and_then(|()| match permissions {
            Some(p) => fs::set_permissions(&tmp, p),
            None => Ok(()),
        })
        .and_then(|()| fs::rename(&tmp, path));
    if result.is_err() {
        let _ = fs::remove_file(&tmp);
    }
    result
}
