//! Markdown file discovery and repository-root detection.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use ignore::WalkBuilder;
use ignore::overrides::OverrideBuilder;
use tracing::warn;

/// Name of the per-directory ignore file (gitignore syntax) that excludes
/// markdown files from checking without touching `.gitignore`.
pub const IGNORE_FILE_NAME: &str = ".mdlinkignore";

/// How directories are walked.
#[derive(Debug, Clone)]
pub struct DiscoverOptions {
    /// Honor `.gitignore`, `.git/info/exclude` and `.mdlinkignore` files.
    pub respect_ignore_files: bool,
    /// Extra gitignore-style globs (relative to each walked path) to skip.
    pub excludes: Vec<String>,
}

impl Default for DiscoverOptions {
    fn default() -> Self {
        Self {
            respect_ignore_files: true,
            excludes: Vec::new(),
        }
    }
}

/// Whether `path` has a markdown extension (`.md` / `.markdown`, any case).
pub fn is_markdown(path: &Path) -> bool {
    path.extension()
        .is_some_and(|ext| ext.eq_ignore_ascii_case("md") || ext.eq_ignore_ascii_case("markdown"))
}

/// Collect markdown files under `paths`, sorted and deduplicated.
///
/// Explicit file arguments are always included when they are markdown, even
/// if an ignore file would exclude them. Directories are walked recursively
/// (following symlinks, including hidden directories such as `.github`, but
/// never descending into `.git`). A path that does not exist is an error.
pub fn find_markdown_files(paths: &[PathBuf], options: &DiscoverOptions) -> Result<Vec<PathBuf>> {
    let mut files = Vec::new();
    for path in paths {
        if path.is_file() {
            if is_markdown(path) {
                files.push(path.clone());
            } else {
                warn!("Skipping non-markdown file {}", path.display());
            }
        } else if path.is_dir() {
            walk(path, options, &mut files)?;
        } else {
            bail!("path does not exist: {}", path.display());
        }
    }
    files.sort();
    files.dedup();
    Ok(files)
}

fn walk(dir: &Path, options: &DiscoverOptions, files: &mut Vec<PathBuf>) -> Result<()> {
    let respect = options.respect_ignore_files;
    let mut builder = WalkBuilder::new(dir);
    builder
        .hidden(false)
        .follow_links(true)
        .ignore(false)
        .git_global(false)
        .git_ignore(respect)
        .git_exclude(respect)
        .parents(respect)
        .require_git(false)
        .filter_entry(|entry| entry.file_name() != ".git");
    if respect {
        builder.add_custom_ignore_filename(IGNORE_FILE_NAME);
    }
    if !options.excludes.is_empty() {
        let mut overrides = OverrideBuilder::new(dir);
        for glob in &options.excludes {
            overrides
                .add(&format!("!{glob}"))
                .with_context(|| format!("invalid --exclude glob '{glob}'"))?;
        }
        builder.overrides(overrides.build()?);
    }

    for entry in builder.build() {
        match entry {
            Ok(entry) => {
                let is_file = entry.file_type().is_some_and(|t| t.is_file());
                if is_file && is_markdown(entry.path()) {
                    files.push(entry.into_path());
                }
            },
            Err(e) => warn!("Skipping unreadable entry: {e}"),
        }
    }
    Ok(())
}

/// Find the repository root for `start`: the nearest ancestor containing a
/// `.git` entry. Falls back to the current directory, which is where
/// `/absolute` links were resolved before root detection existed.
pub fn find_repo_root(start: &Path) -> PathBuf {
    let absolute = std::path::absolute(start).unwrap_or_else(|_| start.to_path_buf());
    let dir = if absolute.is_file() {
        absolute.parent().map(Path::to_path_buf).unwrap_or(absolute)
    } else {
        absolute
    };
    dir.ancestors()
        .find(|p| p.join(".git").exists())
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(root: &Path, files: &[PathBuf]) -> Vec<String> {
        files
            .iter()
            .map(|f| {
                f.strip_prefix(root)
                    .unwrap()
                    .to_string_lossy()
                    .replace('\\', "/")
            })
            .collect()
    }

    fn tree() -> tempfile::TempDir {
        let dir = tempfile::tempdir().unwrap();
        let r = dir.path();
        for p in [
            "a.md",
            "B.MARKDOWN",
            "notes.txt",
            ".github/pr.md",
            ".git/x.md",
            "build/out.md",
            "vendor/v.md",
            "skip/s.md",
        ] {
            let path = r.join(p);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, "x").unwrap();
        }
        std::fs::write(r.join(".gitignore"), "build/\n").unwrap();
        std::fs::write(r.join(IGNORE_FILE_NAME), "skip/\n").unwrap();
        dir
    }

    #[test]
    fn walks_with_ignore_files() {
        let dir = tree();
        let files =
            find_markdown_files(&[dir.path().to_path_buf()], &DiscoverOptions::default()).unwrap();
        assert_eq!(
            names(dir.path(), &files),
            [".github/pr.md", "B.MARKDOWN", "a.md", "vendor/v.md"]
        );
    }

    #[test]
    fn excludes_and_no_ignore_files() {
        let dir = tree();
        let options = DiscoverOptions {
            respect_ignore_files: false,
            excludes: vec!["vendor".into(), ".github/".into()],
        };
        let files = find_markdown_files(&[dir.path().to_path_buf()], &options).unwrap();
        assert_eq!(
            names(dir.path(), &files),
            ["B.MARKDOWN", "a.md", "build/out.md", "skip/s.md"]
        );
    }

    #[test]
    fn explicit_files_and_missing_paths() {
        let dir = tree();
        let skipped = dir.path().join("skip/s.md");
        let files = find_markdown_files(
            &[skipped.clone(), skipped.clone()],
            &DiscoverOptions::default(),
        )
        .unwrap();
        assert_eq!(files, [skipped]);
        let err = find_markdown_files(&[dir.path().join("nope")], &DiscoverOptions::default())
            .unwrap_err();
        assert!(err.to_string().contains("path does not exist"));
    }

    #[test]
    fn repo_root_detection() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::create_dir_all(dir.path().join(".git")).unwrap();
        std::fs::create_dir_all(dir.path().join("docs/deep")).unwrap();
        let root = find_repo_root(&dir.path().join("docs/deep"));
        assert_eq!(root, std::path::absolute(dir.path()).unwrap());
    }
}
