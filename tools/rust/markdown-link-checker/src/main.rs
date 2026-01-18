//! Markdown Link Checker
//!
//! Fast concurrent markdown link validator for CI/CD pipelines.
//!
//! # Features
//!
//! - Recursive markdown file discovery
//! - Concurrent HTTP link validation
//! - Local file link validation
//! - Configurable ignore patterns
//! - JSON output for CI integration
//!
//! # Usage
//!
//! ```bash
//! md-link-checker .                          # Check all markdown files
//! md-link-checker docs/ --internal-only      # Only check internal links
//! md-link-checker README.md --json           # JSON output
//! md-link-checker . --ignore "localhost"     # Custom ignore pattern
//! ```

use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use clap::Parser;
use pulldown_cmark::{Event, Parser as MdParser, Tag};
use regex::Regex;
use reqwest::Client;
use serde::Serialize;
use tokio::sync::Semaphore;
use tracing::{Level, debug, error, info, warn};
use tracing_subscriber::FmtSubscriber;
use walkdir::WalkDir;

/// Fast concurrent markdown link validator
#[derive(Parser, Debug)]
#[command(name = "md-link-checker")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Path to markdown file or directory to check
    #[arg(default_value = ".")]
    path: PathBuf,

    /// Only check internal/local links (skip HTTP/HTTPS)
    #[arg(long)]
    internal_only: bool,

    /// Patterns to ignore (regex)
    #[arg(long, short = 'i')]
    ignore: Vec<String>,

    /// Timeout for HTTP requests in seconds
    #[arg(long, default_value = "10")]
    timeout: u64,

    /// Maximum concurrent HTTP checks
    #[arg(long, default_value = "10")]
    concurrent: usize,

    /// Output results as JSON
    #[arg(long)]
    json: bool,

    /// Enable verbose logging
    #[arg(short, long)]
    verbose: bool,
}

/// Result of checking links in a single file
#[derive(Debug, Serialize)]
struct FileResult {
    file: String,
    links: Vec<LinkResult>,
    broken_count: usize,
    total_count: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

/// Result of checking a single link
#[derive(Debug, Serialize)]
struct LinkResult {
    url: String,
    valid: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

/// Overall check results
#[derive(Debug, Serialize)]
struct CheckResults {
    success: bool,
    files_checked: usize,
    total_links: usize,
    broken_links: usize,
    all_valid: bool,
    results: Vec<FileResult>,
}

/// Default patterns to ignore
const DEFAULT_IGNORE_PATTERNS: &[&str] = &[
    r"^http://localhost",
    r"^http://127\.0\.0\.1",
    r"^http://192\.168\.",
    r"^http://0\.0\.0\.0",
    r"^#",
    r"^mailto:",
    r"^chrome://",
    r"^file://",
    r"^ftp://",
    r"^tel:",
    r"^javascript:",
];

/// Link checker implementation
struct LinkChecker {
    client: Client,
    semaphore: Arc<Semaphore>,
    ignore_patterns: Vec<Regex>,
    check_external: bool,
    timeout: Duration,
}

impl LinkChecker {
    fn new(
        concurrent: usize,
        timeout: Duration,
        ignore_patterns: Vec<String>,
        check_external: bool,
    ) -> Result<Self> {
        let client = Client::builder()
            .timeout(timeout)
            .user_agent("md-link-checker/0.1.0")
            .build()
            .context("Failed to build HTTP client")?;

        // Compile ignore patterns
        let mut compiled_patterns = Vec::new();
        for pattern in DEFAULT_IGNORE_PATTERNS {
            compiled_patterns.push(Regex::new(pattern)?);
        }
        for pattern in &ignore_patterns {
            compiled_patterns.push(Regex::new(pattern)?);
        }

        Ok(Self {
            client,
            semaphore: Arc::new(Semaphore::new(concurrent)),
            ignore_patterns: compiled_patterns,
            check_external,
            timeout,
        })
    }

    /// Find all markdown files in a path
    fn find_markdown_files(&self, path: &Path) -> Vec<PathBuf> {
        let mut files = Vec::new();

        if path.is_file() {
            if let Some(ext) = path.extension()
                && (ext == "md" || ext == "markdown")
            {
                files.push(path.to_path_buf());
            }
        } else if path.is_dir() {
            for entry in WalkDir::new(path)
                .follow_links(true)
                .into_iter()
                .filter_map(|e| e.ok())
            {
                let path = entry.path();
                if path.is_file()
                    && let Some(ext) = path.extension()
                    && (ext == "md" || ext == "markdown")
                {
                    files.push(path.to_path_buf());
                }
            }
        }

        files
    }

    /// Extract links from markdown content
    fn extract_links(&self, content: &str) -> HashSet<String> {
        let mut links = HashSet::new();

        // Remove code blocks to avoid false positives
        let content = remove_code_blocks(content);

        let parser = MdParser::new(&content);

        for event in parser {
            match event {
                Event::Start(Tag::Link { dest_url, .. })
                | Event::Start(Tag::Image { dest_url, .. }) => {
                    let url = dest_url.to_string();
                    if !url.is_empty() {
                        links.insert(url);
                    }
                }
                _ => {}
            }
        }

        // Also extract reference-style links
        let ref_pattern = Regex::new(r"(?m)^\[([^\]]+)\]:\s*(.+)$").unwrap();
        for caps in ref_pattern.captures_iter(&content) {
            if let Some(url) = caps.get(2) {
                let url = url.as_str().trim().to_string();
                if !url.is_empty() {
                    links.insert(url);
                }
            }
        }

        links
    }

    /// Check if a link should be ignored
    fn should_ignore(&self, link: &str) -> bool {
        self.ignore_patterns.iter().any(|p| p.is_match(link))
    }

    /// Check a single link
    async fn check_link(&self, link: &str, base_dir: &Path) -> LinkResult {
        // Check if it's a local file link
        if !link.starts_with("http://") && !link.starts_with("https://") && !link.starts_with("//")
        {
            return self.check_local_link(link, base_dir);
        }

        // Skip external links if configured
        if !self.check_external {
            return LinkResult {
                url: link.to_string(),
                valid: true,
                error: None,
            };
        }

        // Handle protocol-relative URLs
        let url = if link.starts_with("//") {
            format!("https:{}", link)
        } else {
            link.to_string()
        };

        // Acquire semaphore permit for rate limiting
        let _permit = self.semaphore.acquire().await.unwrap();

        // Try HEAD first, then GET
        match self.client.head(&url).send().await {
            Ok(response)
                if response.status().is_success() || response.status().is_redirection() =>
            {
                LinkResult {
                    url: link.to_string(),
                    valid: true,
                    error: None,
                }
            }
            Ok(response) => {
                // Try GET as fallback (some servers don't support HEAD)
                match self.client.get(&url).send().await {
                    Ok(get_response)
                        if get_response.status().is_success()
                            || get_response.status().is_redirection() =>
                    {
                        LinkResult {
                            url: link.to_string(),
                            valid: true,
                            error: None,
                        }
                    }
                    Ok(get_response) => LinkResult {
                        url: link.to_string(),
                        valid: false,
                        error: Some(format!("HTTP {}", get_response.status().as_u16())),
                    },
                    Err(e) => LinkResult {
                        url: link.to_string(),
                        valid: false,
                        error: Some(format!("HTTP {}: {}", response.status().as_u16(), e)),
                    },
                }
            }
            Err(e) => {
                // Try GET as fallback
                match self.client.get(&url).send().await {
                    Ok(response)
                        if response.status().is_success() || response.status().is_redirection() =>
                    {
                        LinkResult {
                            url: link.to_string(),
                            valid: true,
                            error: None,
                        }
                    }
                    Ok(response) => LinkResult {
                        url: link.to_string(),
                        valid: false,
                        error: Some(format!("HTTP {}", response.status().as_u16())),
                    },
                    Err(_) => LinkResult {
                        url: link.to_string(),
                        valid: false,
                        error: Some(e.to_string()),
                    },
                }
            }
        }
    }

    /// Check a local file link
    fn check_local_link(&self, link: &str, base_dir: &Path) -> LinkResult {
        // Remove anchor if present
        let path_str = link.split('#').next().unwrap_or(link);

        let file_path = if let Some(stripped) = path_str.strip_prefix('/') {
            // Absolute path from repo root
            PathBuf::from(stripped)
        } else {
            // Relative to current file
            base_dir.join(path_str)
        };

        if file_path.exists() {
            LinkResult {
                url: link.to_string(),
                valid: true,
                error: None,
            }
        } else {
            LinkResult {
                url: link.to_string(),
                valid: false,
                error: Some("File not found".to_string()),
            }
        }
    }

    /// Check all links in a single file
    async fn check_file(&self, file_path: &Path) -> FileResult {
        let file_str = file_path.display().to_string();

        // Read file content
        let content = match std::fs::read_to_string(file_path) {
            Ok(c) => c,
            Err(e) => {
                return FileResult {
                    file: file_str,
                    links: Vec::new(),
                    broken_count: 0,
                    total_count: 0,
                    error: Some(e.to_string()),
                };
            }
        };

        // Extract links
        let all_links = self.extract_links(&content);
        let base_dir = file_path.parent().unwrap_or(Path::new("."));

        // Filter out ignored links
        let links_to_check: Vec<_> = all_links
            .into_iter()
            .filter(|link| !self.should_ignore(link))
            .collect();

        let total_count = links_to_check.len();

        // Check all links concurrently
        let mut handles = Vec::new();
        for link in links_to_check {
            let checker_link = link.clone();
            let base = base_dir.to_path_buf();
            let client = self.client.clone();
            let semaphore = self.semaphore.clone();
            let check_external = self.check_external;
            let timeout = self.timeout;

            handles.push(tokio::spawn(async move {
                let checker = LinkChecker {
                    client,
                    semaphore,
                    ignore_patterns: Vec::new(),
                    check_external,
                    timeout,
                };
                checker.check_link(&checker_link, &base).await
            }));
        }

        let mut links = Vec::new();
        let mut broken_count = 0;

        for handle in handles {
            match handle.await {
                Ok(result) => {
                    if !result.valid {
                        broken_count += 1;
                    }
                    links.push(result);
                }
                Err(e) => {
                    links.push(LinkResult {
                        url: "unknown".to_string(),
                        valid: false,
                        error: Some(format!("Task failed: {}", e)),
                    });
                    broken_count += 1;
                }
            }
        }

        FileResult {
            file: file_str,
            links,
            broken_count,
            total_count,
            error: None,
        }
    }

    /// Check all markdown files in a path
    async fn check_all(&self, path: &Path) -> CheckResults {
        let files = self.find_markdown_files(path);

        if files.is_empty() {
            return CheckResults {
                success: true,
                files_checked: 0,
                total_links: 0,
                broken_links: 0,
                all_valid: true,
                results: Vec::new(),
            };
        }

        info!("Found {} markdown files to check", files.len());

        let mut results = Vec::new();
        let mut total_links = 0;
        let mut broken_links = 0;

        for file in &files {
            debug!("Checking {}", file.display());
            let file_result = self.check_file(file).await;
            total_links += file_result.total_count;
            broken_links += file_result.broken_count;

            if file_result.broken_count > 0 {
                warn!(
                    "{}: {} broken link(s)",
                    file.display(),
                    file_result.broken_count
                );
            }

            results.push(file_result);
        }

        CheckResults {
            success: true,
            files_checked: files.len(),
            total_links,
            broken_links,
            all_valid: broken_links == 0,
            results,
        }
    }
}

/// Remove code blocks from markdown to avoid false positives
fn remove_code_blocks(content: &str) -> String {
    // Remove fenced code blocks
    let fenced = Regex::new(r"```[\s\S]*?```").unwrap();
    let content = fenced.replace_all(content, "");

    // Remove inline code
    let inline = Regex::new(r"`[^`]+`").unwrap();
    inline.replace_all(&content, "").to_string()
}

fn setup_logging(verbose: bool) {
    let level = if verbose { Level::DEBUG } else { Level::INFO };

    let subscriber = FmtSubscriber::builder()
        .with_max_level(level)
        .with_target(false)
        .with_thread_ids(false)
        .with_file(false)
        .with_line_number(false)
        .finish();

    tracing::subscriber::set_global_default(subscriber).ok();
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();

    // Setup logging (skip if JSON output to keep stdout clean)
    if !args.json {
        setup_logging(args.verbose);
    }

    // Create checker
    let checker = LinkChecker::new(
        args.concurrent,
        Duration::from_secs(args.timeout),
        args.ignore,
        !args.internal_only,
    )?;

    // Run checks
    let results = checker.check_all(&args.path).await;

    // Output results
    if args.json {
        println!("{}", serde_json::to_string_pretty(&results)?);
    } else {
        // Human-readable output
        println!();
        println!("=== Markdown Link Check Results ===");
        println!();
        println!("Files checked: {}", results.files_checked);
        println!("Total links:   {}", results.total_links);
        println!("Broken links:  {}", results.broken_links);
        println!();

        if results.broken_links > 0 {
            println!("Broken links:");
            println!();
            for file_result in &results.results {
                for link in &file_result.links {
                    if !link.valid {
                        println!(
                            "  {} -> {} ({})",
                            file_result.file,
                            link.url,
                            link.error.as_deref().unwrap_or("unknown error")
                        );
                    }
                }
            }
            println!();
            error!(
                "Link check failed with {} broken link(s)",
                results.broken_links
            );
            std::process::exit(1);
        } else {
            info!("All links valid!");
        }
    }

    if !results.all_valid {
        std::process::exit(1);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_links() {
        let checker = LinkChecker::new(1, Duration::from_secs(10), Vec::new(), true).unwrap();

        let content = r#"
# Test

[Link 1](https://example.com)
[Link 2](./local.md)
![Image](https://example.com/image.png)

[ref]: https://reference.com
"#;

        let links = checker.extract_links(content);
        assert!(links.contains("https://example.com"));
        assert!(links.contains("./local.md"));
        assert!(links.contains("https://example.com/image.png"));
        assert!(links.contains("https://reference.com"));
    }

    #[test]
    fn test_should_ignore() {
        let checker = LinkChecker::new(1, Duration::from_secs(10), Vec::new(), true).unwrap();

        assert!(checker.should_ignore("http://localhost:8080"));
        assert!(checker.should_ignore("mailto:test@example.com"));
        assert!(checker.should_ignore("#anchor"));
        assert!(!checker.should_ignore("https://example.com"));
    }

    #[test]
    fn test_remove_code_blocks() {
        let content = r#"
Normal [link](https://example.com)

```python
fake_link = "[not a link](https://fake.com)"
```

More `inline [code](https://also-fake.com)` here
"#;

        let cleaned = remove_code_blocks(content);
        assert!(cleaned.contains("https://example.com"));
        assert!(!cleaned.contains("https://fake.com"));
        assert!(!cleaned.contains("https://also-fake.com"));
    }

    #[test]
    fn test_check_local_link() {
        let checker = LinkChecker::new(1, Duration::from_secs(10), Vec::new(), true).unwrap();

        // Check that Cargo.toml exists (it should)
        let result = checker.check_local_link("Cargo.toml", Path::new("."));
        assert!(result.valid);

        // Check non-existent file
        let result = checker.check_local_link("nonexistent.txt", Path::new("."));
        assert!(!result.valid);
    }
}
