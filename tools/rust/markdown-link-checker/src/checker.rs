//! Orchestration: parse every file, check local links immediately, and check
//! each unique external URL exactly once no matter how many files use it.

use std::collections::{BTreeSet, HashMap};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::Result;
use tokio::task::JoinSet;
use tracing::{debug, info, warn};

use crate::discover::{DiscoverOptions, find_markdown_files};
use crate::filters::IgnoreRules;
use crate::http::{HttpChecker, HttpOptions};
use crate::local::LocalChecker;
use crate::parse::parse_document;
use crate::report::{CheckResults, FileResult, LinkResult};
use crate::target::{LinkTarget, classify, strip_fragment};

/// Everything that controls a run.
#[derive(Debug, Clone)]
pub struct CheckOptions {
    /// Validate `http(s)` links (false = `--internal-only`).
    pub check_external: bool,
    /// Validate `#fragments` against headings (false = `--skip-anchors`).
    pub validate_anchors: bool,
    /// Report `[text][label]` references whose label is never defined.
    pub check_undefined_refs: bool,
    /// Directory that `/absolute` links resolve against.
    pub root: PathBuf,
    /// Links to skip entirely.
    pub ignore: IgnoreRules,
    /// External checking tunables.
    pub http: HttpOptions,
    /// File discovery settings.
    pub discover: DiscoverOptions,
}

/// Discover markdown files under `paths` and check them.
pub async fn check_paths(paths: &[PathBuf], options: &CheckOptions) -> Result<CheckResults> {
    let files = find_markdown_files(paths, &options.discover)?;
    info!("Found {} markdown files to check", files.len());
    check_files(&files, options).await
}

/// Where a link's final result comes from.
enum Pending {
    Done(LinkResult),
    Http {
        url: String,
        lines: Vec<usize>,
        key: String,
    },
}

/// Check an explicit list of markdown files.
pub async fn check_files(files: &[PathBuf], options: &CheckOptions) -> Result<CheckResults> {
    let mut local = LocalChecker::new(options.root.clone(), options.validate_anchors);
    let mut staged: Vec<(String, Result<Vec<Pending>, String>)> = Vec::new();
    let mut external: BTreeSet<String> = BTreeSet::new();

    for file in files {
        debug!("Checking {}", file.display());
        let name = file.display().to_string();
        let pending = stage_file(file, options, &mut local, &mut external);
        staged.push((name, pending));
    }

    let http_results = check_external(external, &options.http).await?;

    let results = staged
        .into_iter()
        .map(|(name, pending)| match pending {
            Err(e) => FileResult::unreadable(name, e),
            Ok(items) => {
                let links = items
                    .into_iter()
                    .map(|item| match item {
                        Pending::Done(result) => result,
                        Pending::Http { url, lines, key } => {
                            let outcome = http_results
                                .get(&key)
                                .cloned()
                                .unwrap_or_else(|| Err("URL was not checked".to_string()));
                            LinkResult::from_outcome(url, lines, outcome)
                        },
                    })
                    .collect();
                let result = FileResult::new(name, links);
                if result.broken_count > 0 {
                    warn!("{}: {} broken link(s)", result.file, result.broken_count);
                }
                result
            },
        })
        .collect();

    Ok(CheckResults::from_files(results))
}

/// Parse one file and resolve everything that does not need the network.
fn stage_file(
    file: &Path,
    options: &CheckOptions,
    local: &mut LocalChecker,
    external: &mut BTreeSet<String>,
) -> Result<Vec<Pending>, String> {
    let content = std::fs::read_to_string(file).map_err(|e| e.to_string())?;
    let doc = parse_document(&content);
    let base_dir = file.parent().unwrap_or(Path::new("."));
    let mut pending = Vec::with_capacity(doc.links.len());

    for link in doc.links {
        if options.ignore.is_ignored(&link.url) {
            continue;
        }
        let item = match classify(&link.url) {
            LinkTarget::Unsupported => continue,
            LinkTarget::SamePage { anchor } => {
                let outcome = local.check_same_page(&anchor, &doc.anchors);
                Pending::Done(LinkResult::from_outcome(link.url, link.lines, outcome))
            },
            LinkTarget::Local { path, anchor } => {
                let outcome = local.check_path(&path, anchor.as_deref(), base_dir);
                Pending::Done(LinkResult::from_outcome(link.url, link.lines, outcome))
            },
            LinkTarget::External { url } => {
                if options.check_external {
                    let key = strip_fragment(&url).to_string();
                    external.insert(key.clone());
                    Pending::Http {
                        url: link.url,
                        lines: link.lines,
                        key,
                    }
                } else {
                    let mut result = LinkResult::ok(link.url, link.lines);
                    result.skipped = true;
                    Pending::Done(result)
                }
            },
        };
        pending.push(item);
    }

    if options.check_undefined_refs {
        for reference in doc.undefined_references {
            if options.ignore.is_ignored(&reference.text) {
                continue;
            }
            pending.push(Pending::Done(LinkResult::broken(
                reference.text,
                vec![reference.line],
                "Undefined link reference (rendered as plain text)".to_string(),
            )));
        }
    }

    local.remember_anchors(file, doc.anchors);
    Ok(pending)
}

/// Check each unique URL once, concurrently.
async fn check_external(
    urls: BTreeSet<String>,
    options: &HttpOptions,
) -> Result<HashMap<String, Result<(), String>>> {
    let mut results = HashMap::with_capacity(urls.len());
    if urls.is_empty() {
        return Ok(results);
    }
    info!("Checking {} unique external URLs", urls.len());

    let checker = Arc::new(HttpChecker::new(options.clone())?);
    let mut tasks = JoinSet::new();
    for url in urls {
        let checker = Arc::clone(&checker);
        tasks.spawn(async move {
            let outcome = checker.check(&url).await;
            debug!("{url}: {outcome:?}");
            (url, outcome)
        });
    }
    while let Some(joined) = tasks.join_next().await {
        match joined {
            Ok((url, outcome)) => {
                results.insert(url, outcome);
            },
            Err(e) => warn!("URL check task failed: {e}"),
        }
    }
    Ok(results)
}
