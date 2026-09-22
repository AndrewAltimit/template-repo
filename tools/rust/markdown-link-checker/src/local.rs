//! Validation of local file links and fragments.

use std::collections::{HashMap, HashSet};
use std::ffi::OsString;
use std::path::{Component, Path, PathBuf};
use std::rc::Rc;

use crate::discover::is_markdown;
use crate::parse::heading_anchors;

/// Checks local paths and anchors, caching directory listings and the
/// anchors of every markdown file it has read.
#[derive(Debug)]
pub struct LocalChecker {
    root: PathBuf,
    validate_anchors: bool,
    anchors: HashMap<PathBuf, Result<Rc<HashSet<String>>, String>>,
    listings: HashMap<PathBuf, Option<Vec<OsString>>>,
}

impl LocalChecker {
    /// `root` resolves `/absolute` links; `validate_anchors` enables fragment
    /// checks.
    pub fn new(root: PathBuf, validate_anchors: bool) -> Self {
        Self {
            root,
            validate_anchors,
            anchors: HashMap::new(),
            listings: HashMap::new(),
        }
    }

    /// Seed the anchor cache with a document that has already been parsed.
    pub fn remember_anchors(&mut self, file: &Path, anchors: HashSet<String>) {
        self.anchors
            .insert(file.to_path_buf(), Ok(Rc::new(anchors)));
    }

    /// Validate a same-document fragment.
    pub fn check_same_page(&self, anchor: &str, anchors: &HashSet<String>) -> Result<(), String> {
        if !self.validate_anchors || anchor_exists(anchor, anchors) {
            return Ok(());
        }
        Err(format!(
            "Anchor not found in document headings{}",
            suggestion(anchor, anchors)
        ))
    }

    /// Validate a path (relative to `base_dir`, or to the root when it starts
    /// with `/`) and its optional fragment.
    pub fn check_path(
        &mut self,
        path: &str,
        anchor: Option<&str>,
        base_dir: &Path,
    ) -> Result<(), String> {
        let (base, rel) = match path.strip_prefix('/') {
            Some(stripped) => (self.root.clone(), stripped),
            None => (base_dir.to_path_buf(), path),
        };
        let file_path = base.join(rel);

        let metadata = std::fs::metadata(&file_path).map_err(|_| "File not found".to_string())?;
        if let Some((written, actual)) = self.case_mismatch(&base, Path::new(rel)) {
            return Err(format!(
                "File not found (case mismatch: '{written}' is '{actual}' on disk)"
            ));
        }

        let Some(anchor) = anchor.filter(|_| self.validate_anchors) else {
            return Ok(());
        };

        // A directory link shows its README on GitHub, so fragments target it.
        let doc = if metadata.is_dir() {
            match find_readme(&file_path) {
                Some(readme) => readme,
                None => return Ok(()),
            }
        } else if is_markdown(&file_path) {
            file_path
        } else {
            // Fragments into source files (`#L10-L20`) cannot be validated.
            return Ok(());
        };

        let anchors = self.anchors_of(&doc)?;
        if anchor_exists(anchor, &anchors) {
            Ok(())
        } else {
            Err(format!(
                "Anchor #{anchor} not found in {}{}",
                doc.display(),
                suggestion(anchor, &anchors)
            ))
        }
    }

    fn anchors_of(&mut self, doc: &Path) -> Result<Rc<HashSet<String>>, String> {
        self.anchors
            .entry(doc.to_path_buf())
            .or_insert_with(|| {
                std::fs::read_to_string(doc)
                    .map(|content| Rc::new(heading_anchors(&content)))
                    .map_err(|e| {
                        format!("Cannot read {} for anchor validation: {e}", doc.display())
                    })
            })
            .clone()
    }

    /// Return `(written, on_disk)` for the first component of `rel` whose
    /// case differs from the directory entry. This catches links that work
    /// on case-insensitive filesystems (Windows, macOS) but break on GitHub.
    fn case_mismatch(&mut self, base: &Path, rel: &Path) -> Option<(String, String)> {
        let mut current = base.to_path_buf();
        for component in rel.components() {
            if let Component::Normal(name) = component {
                let dir = if current.as_os_str().is_empty() {
                    PathBuf::from(".")
                } else {
                    current.clone()
                };
                if let Some(entries) = self.listing(&dir)
                    && !entries.iter().any(|e| e == name)
                {
                    let wanted = name.to_string_lossy().to_lowercase();
                    if let Some(actual) = entries
                        .iter()
                        .find(|e| e.to_string_lossy().to_lowercase() == wanted)
                    {
                        return Some((
                            name.to_string_lossy().into_owned(),
                            actual.to_string_lossy().into_owned(),
                        ));
                    }
                }
            }
            current.push(component);
        }
        None
    }

    fn listing(&mut self, dir: &Path) -> Option<&Vec<OsString>> {
        self.listings
            .entry(dir.to_path_buf())
            .or_insert_with(|| {
                std::fs::read_dir(dir)
                    .ok()
                    .map(|rd| rd.filter_map(|e| e.ok().map(|e| e.file_name())).collect())
            })
            .as_ref()
    }
}

/// Whether `anchor` resolves: an empty fragment and `#top` scroll to the top
/// of the page, and GitHub accepts its `user-content-` prefix explicitly.
fn anchor_exists(anchor: &str, anchors: &HashSet<String>) -> bool {
    anchor.is_empty()
        || anchor.eq_ignore_ascii_case("top")
        || anchors.contains(anchor)
        || anchor
            .strip_prefix("user-content-")
            .is_some_and(|a| anchors.contains(a))
}

fn find_readme(dir: &Path) -> Option<PathBuf> {
    let entries = std::fs::read_dir(dir).ok()?;
    entries.filter_map(Result::ok).map(|e| e.path()).find(|p| {
        p.file_stem()
            .is_some_and(|s| s.eq_ignore_ascii_case("readme"))
            && is_markdown(p)
    })
}

/// Build a `" (did you mean #x?)"` hint for a near-miss anchor.
fn suggestion(anchor: &str, anchors: &HashSet<String>) -> String {
    let wanted = anchor.to_lowercase();
    let budget = (wanted.chars().count() / 4).max(2);
    anchors
        .iter()
        .map(|a| (edit_distance(&wanted, a), a))
        .filter(|&(d, _)| d <= budget)
        .min_by(|x, y| x.0.cmp(&y.0).then_with(|| x.1.cmp(y.1)))
        .map(|(_, a)| format!(" (did you mean #{a}?)"))
        .unwrap_or_default()
}

/// Levenshtein distance over chars.
fn edit_distance(a: &str, b: &str) -> usize {
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut cur = vec![0; b.len() + 1];
    for (i, ca) in a.chars().enumerate() {
        cur[0] = i + 1;
        for (j, &cb) in b.iter().enumerate() {
            let cost = usize::from(ca != cb);
            cur[j + 1] = (prev[j] + cost).min(prev[j + 1] + 1).min(cur[j] + 1);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[b.len()]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn set(items: &[&str]) -> HashSet<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn same_page_anchors() {
        let checker = LocalChecker::new(PathBuf::from("."), true);
        let anchors = set(&["introduction", "conclusion"]);
        assert!(checker.check_same_page("introduction", &anchors).is_ok());
        assert!(checker.check_same_page("", &anchors).is_ok());
        assert!(checker.check_same_page("top", &anchors).is_ok());
        assert!(
            checker
                .check_same_page("user-content-conclusion", &anchors)
                .is_ok()
        );
        let err = checker
            .check_same_page("introductoin", &anchors)
            .unwrap_err();
        assert!(
            err.contains("Anchor not found in document headings"),
            "{err}"
        );
        assert!(err.contains("did you mean #introduction?"), "{err}");
        let err = checker.check_same_page("zzz", &anchors).unwrap_err();
        assert!(!err.contains("did you mean"), "{err}");
    }

    #[test]
    fn same_page_disabled() {
        let checker = LocalChecker::new(PathBuf::from("."), false);
        assert!(checker.check_same_page("nope", &HashSet::new()).is_ok());
    }

    #[test]
    fn paths_and_anchors() {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path();
        std::fs::create_dir_all(root.join("docs/sub")).unwrap();
        std::fs::write(root.join("docs/Guide.md"), "# Getting Started\n## Setup\n").unwrap();
        std::fs::write(root.join("docs/sub/README.md"), "# Sub Docs\n").unwrap();
        std::fs::write(root.join("docs/code.rs"), "fn main() {}\n").unwrap();
        std::fs::write(root.join("docs/my file.md"), "x\n").unwrap();

        let mut c = LocalChecker::new(root.to_path_buf(), true);
        let docs = root.join("docs");
        assert!(c.check_path("Guide.md", None, &docs).is_ok());
        assert!(c.check_path("Guide.md", Some("setup"), &docs).is_ok());
        assert!(
            c.check_path("./Guide.md", Some("getting-started"), &docs)
                .is_ok()
        );
        assert!(
            c.check_path("/docs/Guide.md", Some("setup"), Path::new("elsewhere"))
                .is_ok()
        );
        assert!(c.check_path("sub", Some("sub-docs"), &docs).is_ok());
        assert!(c.check_path("sub/", None, &docs).is_ok());
        assert!(c.check_path("code.rs", Some("L1-L3"), &docs).is_ok());
        assert!(c.check_path("my file.md", None, &docs).is_ok());
        assert!(c.check_path("../docs/Guide.md", None, &docs).is_ok());

        let err = c.check_path("Guide.md", Some("setpu"), &docs).unwrap_err();
        assert!(err.contains("Anchor #setpu not found"), "{err}");
        assert!(err.contains("did you mean #setup?"), "{err}");
        assert!(c.check_path("sub", Some("missing"), &docs).is_err());
        assert_eq!(
            c.check_path("missing.md", None, &docs).unwrap_err(),
            "File not found"
        );

        let mut off = LocalChecker::new(root.to_path_buf(), false);
        assert!(off.check_path("Guide.md", Some("nope"), &docs).is_ok());
    }

    #[test]
    fn case_mismatch_detected() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::create_dir_all(dir.path().join("Docs")).unwrap();
        std::fs::write(dir.path().join("Docs/Readme.md"), "# X\n").unwrap();
        let mut c = LocalChecker::new(dir.path().to_path_buf(), true);
        // On case-sensitive filesystems this is plain "File not found"; on
        // case-insensitive ones the mismatch is reported explicitly.
        let err = c
            .check_path("docs/readme.md", None, dir.path())
            .unwrap_err();
        assert!(err.starts_with("File not found"), "{err}");
        assert!(c.check_path("Docs/Readme.md", None, dir.path()).is_ok());
    }

    #[test]
    fn edit_distance_works() {
        assert_eq!(edit_distance("kitten", "sitting"), 3);
        assert_eq!(edit_distance("", "abc"), 3);
        assert_eq!(edit_distance("same", "same"), 0);
    }
}
