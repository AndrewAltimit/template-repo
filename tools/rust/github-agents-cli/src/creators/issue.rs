//! Issue creator for automated issue generation from analysis findings.
//!
//! This module handles:
//! - Creating GitHub issues from analysis findings
//! - Deduplication against existing issues (fingerprint markers)
//! - Adding issues to the project board (via `board-manager`)

use std::collections::HashSet;
use std::io::Write;

use chrono::{Duration, Utc};
use serde::{Deserialize, Serialize};
use tracing::{debug, error, info, warn};

use crate::analyzers::{AnalysisFinding, FindingCategory, FindingPriority};
use crate::error::Error;
use crate::utils::text::truncate_str;
use crate::utils::{run_gh_command, run_gh_command_with_stderr};

/// Result of issue creation attempt.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreationResult {
    /// The finding that was processed.
    pub finding: AnalysisFinding,
    /// Issue number if created.
    pub issue_number: Option<u64>,
    /// Issue URL if created.
    pub issue_url: Option<String>,
    /// Whether the issue was created.
    pub created: bool,
    /// Reason for skipping if not created.
    pub skipped_reason: Option<String>,
    /// Issue number of duplicate if found.
    pub duplicate_of: Option<u64>,
}

impl CreationResult {
    /// Create a skipped result.
    pub fn skipped(finding: AnalysisFinding, reason: impl Into<String>) -> Self {
        Self {
            finding,
            issue_number: None,
            issue_url: None,
            created: false,
            skipped_reason: Some(reason.into()),
            duplicate_of: None,
        }
    }

    /// Create a success result.
    pub fn success(finding: AnalysisFinding, issue_number: u64, issue_url: String) -> Self {
        Self {
            finding,
            issue_number: Some(issue_number),
            issue_url: Some(issue_url),
            created: true,
            skipped_reason: None,
            duplicate_of: None,
        }
    }
}

/// Issue size for board.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IssueSize {
    XS,
    S,
    M,
    L,
    XL,
}

impl IssueSize {
    pub fn value(&self) -> &'static str {
        match self {
            IssueSize::XS => "XS",
            IssueSize::S => "S",
            IssueSize::M => "M",
            IssueSize::L => "L",
            IssueSize::XL => "XL",
        }
    }
}

/// Issue type for board.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IssueType {
    Bug,
    TechDebt,
    Documentation,
}

impl IssueType {
    pub fn value(&self) -> &'static str {
        match self {
            IssueType::Bug => "Bug",
            IssueType::TechDebt => "Tech Debt",
            IssueType::Documentation => "Documentation",
        }
    }
}

/// Issue priority for board.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IssuePriority {
    Critical,
    High,
    Medium,
    Low,
}

impl IssuePriority {
    pub fn value(&self) -> &'static str {
        match self {
            IssuePriority::Critical => "Critical",
            IssuePriority::High => "High",
            IssuePriority::Medium => "Medium",
            IssuePriority::Low => "Low",
        }
    }
}

/// Default labels for automated issues.
const DEFAULT_LABELS: &[&str] = &["automated", "needs-review", "agentic-analysis"];

/// Label colors (hex, no `#`).
const LABEL_COLORS: &[(&str, &str)] = &[
    ("automated", "0366d6"),
    ("needs-review", "fbca04"),
    ("agentic-analysis", "5319e7"),
    ("category:security", "d73a4a"),
    ("category:performance", "a2eeef"),
    ("category:quality", "7057ff"),
    ("category:tech_debt", "008672"),
    ("category:documentation", "0075ca"),
    ("category:testing", "bfd4f2"),
    ("category:architecture", "d4c5f9"),
    ("category:dependency", "c5def5"),
    ("priority:critical", "b60205"),
    ("priority:high", "d93f0b"),
    ("priority:medium", "fbca04"),
    ("priority:low", "0e8a16"),
];

/// Creates GitHub issues from analysis findings with deduplication.
pub struct IssueCreator {
    /// Repository in owner/repo format.
    pub repo: String,
    /// Days to look back for duplicate checking.
    pub lookback_days: i64,
    /// Minimum priority to create issues for.
    pub min_priority: FindingPriority,
    /// Maximum issues to create in one run.
    pub max_issues_per_run: usize,
    /// If true, don't actually create issues.
    pub dry_run: bool,

    created_count: usize,
    known_fingerprints: HashSet<String>,
}

impl IssueCreator {
    /// Create a new issue creator.
    pub fn new(repo: impl Into<String>) -> Self {
        Self {
            repo: repo.into(),
            lookback_days: 30,
            min_priority: FindingPriority::P3,
            max_issues_per_run: 5,
            dry_run: false,
            created_count: 0,
            known_fingerprints: HashSet::new(),
        }
    }

    /// Set minimum priority threshold.
    pub fn with_min_priority(mut self, priority: FindingPriority) -> Self {
        self.min_priority = priority;
        self
    }

    /// Set maximum issues per run.
    pub fn with_max_issues(mut self, max: usize) -> Self {
        self.max_issues_per_run = max;
        self
    }

    /// Enable dry run mode.
    pub fn with_dry_run(mut self, dry_run: bool) -> Self {
        self.dry_run = dry_run;
        self
    }

    fn priority_label(priority: FindingPriority) -> &'static str {
        match priority {
            FindingPriority::P0 => "priority:critical",
            FindingPriority::P1 => "priority:high",
            FindingPriority::P2 => "priority:medium",
            FindingPriority::P3 => "priority:low",
        }
    }

    fn priority_to_board(priority: FindingPriority) -> IssuePriority {
        match priority {
            FindingPriority::P0 => IssuePriority::Critical,
            FindingPriority::P1 => IssuePriority::High,
            FindingPriority::P2 => IssuePriority::Medium,
            FindingPriority::P3 => IssuePriority::Low,
        }
    }

    fn category_to_type(category: FindingCategory) -> IssueType {
        match category {
            FindingCategory::Security | FindingCategory::Performance => IssueType::Bug,
            FindingCategory::Documentation => IssueType::Documentation,
            FindingCategory::Quality
            | FindingCategory::TechDebt
            | FindingCategory::Testing
            | FindingCategory::Architecture
            | FindingCategory::Dependency => IssueType::TechDebt,
        }
    }

    /// Estimate issue size based on number of affected files.
    fn estimate_size(finding: &AnalysisFinding) -> IssueSize {
        match finding.affected_files.len() {
            0..=1 => IssueSize::XS,
            2..=3 => IssueSize::S,
            4..=6 => IssueSize::M,
            7..=10 => IssueSize::L,
            _ => IssueSize::XL,
        }
    }

    /// Create GitHub issues from findings (highest priority first).
    pub async fn create_issues(
        &mut self,
        findings: Vec<AnalysisFinding>,
    ) -> Result<Vec<CreationResult>, Error> {
        self.load_existing_fingerprints().await;

        if !self.dry_run {
            let mut labels: Vec<String> = DEFAULT_LABELS.iter().map(|s| s.to_string()).collect();
            for f in &findings {
                labels.push(format!("category:{}", f.category.value()));
                labels.push(Self::priority_label(f.priority).to_string());
            }
            labels.sort();
            labels.dedup();
            self.ensure_labels_exist(&labels).await;
        }

        let mut sorted = findings;
        sorted.sort_by_key(|f| f.priority);

        let mut results = Vec::with_capacity(sorted.len());
        for finding in sorted {
            if self.created_count >= self.max_issues_per_run {
                results.push(CreationResult::skipped(
                    finding,
                    "max_issues_per_run limit reached",
                ));
                continue;
            }
            let result = self.process_finding(finding).await;
            if result.created {
                self.created_count += 1;
            }
            results.push(result);
        }
        Ok(results)
    }

    /// Process a single finding for issue creation.
    async fn process_finding(&mut self, finding: AnalysisFinding) -> CreationResult {
        if finding.priority > self.min_priority {
            let reason = format!("below min priority ({})", finding.priority.value());
            return CreationResult::skipped(finding, reason);
        }

        let fingerprint = finding.fingerprint();
        if !self.known_fingerprints.insert(fingerprint.clone()) {
            return CreationResult::skipped(finding, "exact duplicate (fingerprint match)");
        }

        if self.dry_run {
            info!("[DRY RUN] Would create issue: {}", finding.to_issue_title());
            return CreationResult::skipped(finding, "dry run mode");
        }

        match self.create_github_issue(&finding).await {
            Ok((number, url)) => {
                self.add_to_board_best_effort(&finding, number).await;
                CreationResult::success(finding, number, url)
            },
            Err(reason) => {
                // Allow a retry of this fingerprint in a later run
                self.known_fingerprints.remove(&fingerprint);
                error!("Failed to create issue: {}", reason);
                CreationResult::skipped(finding, reason)
            },
        }
    }

    /// Create a GitHub issue for the finding; returns (number, url) or a
    /// human-readable failure reason.
    async fn create_github_issue(
        &self,
        finding: &AnalysisFinding,
    ) -> Result<(u64, String), String> {
        let title = finding.to_issue_title();
        let labels = format!(
            "{},category:{},{}",
            DEFAULT_LABELS.join(","),
            finding.category.value(),
            Self::priority_label(finding.priority)
        );

        let mut body_file = tempfile::Builder::new()
            .prefix("github-agents-issue-")
            .suffix(".md")
            .tempfile()
            .map_err(|e| format!("temp file error: {}", e))?;
        body_file
            .write_all(finding.to_issue_body().as_bytes())
            .map_err(|e| format!("temp file error: {}", e))?;
        let body_path = body_file.path().to_string_lossy().into_owned();

        let args = [
            "issue",
            "create",
            "--repo",
            &self.repo,
            "--title",
            &title,
            "--body-file",
            &body_path,
            "--label",
            &labels,
        ];
        let (stdout, stderr, code) = run_gh_command_with_stderr(&args)
            .await
            .map_err(|e| format!("creation failed: {}", e))?;

        if code != 0 {
            let msg = stderr
                .or(stdout)
                .unwrap_or_else(|| "unknown error".to_string());
            return Err(format!(
                "gh failed (exit {}): {}",
                code,
                truncate_str(&msg, 100)
            ));
        }

        let url = stdout.ok_or_else(|| {
            format!(
                "gh returned empty output: {}",
                truncate_str(stderr.as_deref().unwrap_or("no output"), 100)
            )
        })?;
        let number = parse_issue_number(&url)
            .ok_or_else(|| format!("failed to parse issue URL: {:?}", url))?;

        info!("Created issue #{}: {}", number, title);
        Ok((number, url))
    }

    async fn add_to_board_best_effort(&self, finding: &AnalysisFinding, number: u64) {
        if let Err(e) = add_to_board(
            number,
            Self::priority_to_board(finding.priority),
            Self::category_to_type(finding.category),
            Self::estimate_size(finding),
            "Claude Code",
        )
        .await
        {
            warn!("Failed to add issue #{} to board: {}", number, e);
        }
    }

    /// Ensure all required labels exist in the repository.
    async fn ensure_labels_exist(&self, labels: &[String]) {
        let endpoint = format!("repos/{}/labels", self.repo);
        for label in labels {
            let color = LABEL_COLORS
                .iter()
                .find(|(name, _)| name == label)
                .map(|(_, c)| *c)
                .unwrap_or("ededed");
            let name_field = format!("name={}", label);
            let color_field = format!("color={}", color);
            // 422 means the label already exists; nothing to do
            let _ = run_gh_command(
                &[
                    "api",
                    &endpoint,
                    "-X",
                    "POST",
                    "-f",
                    &name_field,
                    "-f",
                    &color_field,
                ],
                false,
            )
            .await;
        }
    }

    /// Load fingerprints from existing issues for deduplication.
    async fn load_existing_fingerprints(&mut self) {
        #[derive(Deserialize)]
        struct IssueData {
            body: Option<String>,
        }

        let cutoff = (Utc::now() - Duration::days(self.lookback_days)).format("%Y-%m-%d");
        let search_query = format!("created:>={}", cutoff);
        let args = [
            "issue",
            "list",
            "--repo",
            &self.repo,
            "--state",
            "all",
            "--label",
            "agentic-analysis",
            "--search",
            &search_query,
            "--json",
            "number,body",
            "--limit",
            "200",
        ];

        let output = match run_gh_command(&args, false).await {
            Ok(Some(o)) => o,
            Ok(None) => {
                warn!("Could not list existing issues; duplicate detection limited to this run");
                return;
            },
            Err(e) => {
                warn!("Failed to load existing fingerprints: {}", e);
                return;
            },
        };

        match serde_json::from_str::<Vec<IssueData>>(output.trim()) {
            Ok(issues) => {
                self.known_fingerprints.extend(
                    issues
                        .iter()
                        .filter_map(|i| i.body.as_deref().and_then(extract_fingerprint)),
                );
                info!(
                    "Loaded {} existing fingerprints",
                    self.known_fingerprints.len()
                );
            },
            Err(e) => warn!("Failed to parse existing issues: {}", e),
        }
    }
}

/// Extract `<!-- analysis-fingerprint:HEX -->` from an issue body.
fn extract_fingerprint(body: &str) -> Option<String> {
    const MARKER: &str = "analysis-fingerprint:";
    let start = body.find(MARKER)? + MARKER.len();
    let rest = &body[start..];
    let fp = rest[..rest.find("-->")?].trim();
    (!fp.is_empty() && fp.chars().all(|c| c.is_ascii_hexdigit())).then(|| fp.to_string())
}

/// Parse the issue number from a `.../issues/123` URL printed by `gh`.
fn parse_issue_number(url: &str) -> Option<u64> {
    url.trim()
        .trim_end_matches('/')
        .rsplit('/')
        .next()?
        .parse()
        .ok()
}

/// Add an issue to the project board via the `board-manager` CLI.
async fn add_to_board(
    issue_number: u64,
    priority: IssuePriority,
    issue_type: IssueType,
    size: IssueSize,
    agent: &str,
) -> Result<(), Error> {
    use std::process::Stdio;
    use tokio::process::Command;

    let number = issue_number.to_string();
    let args = [
        "add",
        &number,
        "--priority",
        priority.value(),
        "--type",
        issue_type.value(),
        "--size",
        size.value(),
        "--agent",
        agent,
    ];
    debug!("Running: board-manager {}", args.join(" "));

    let output = Command::new("board-manager")
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .output()
        .await
        .map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                Error::Board("board-manager binary not found in PATH".to_string())
            } else {
                Error::Io(e)
            }
        })?;

    if output.status.success() {
        info!(
            "Added issue #{} to board with priority={}, type={}, size={}",
            issue_number,
            priority.value(),
            issue_type.value(),
            size.value()
        );
        Ok(())
    } else {
        Err(Error::Board(format!(
            "board-manager failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::analyzers::{AffectedFile, test_finding};

    #[test]
    fn test_priority_label() {
        assert_eq!(
            IssueCreator::priority_label(FindingPriority::P0),
            "priority:critical"
        );
        assert_eq!(
            IssueCreator::priority_label(FindingPriority::P3),
            "priority:low"
        );
    }

    #[test]
    fn test_priority_to_board() {
        assert_eq!(
            IssueCreator::priority_to_board(FindingPriority::P0),
            IssuePriority::Critical
        );
        assert_eq!(
            IssueCreator::priority_to_board(FindingPriority::P1),
            IssuePriority::High
        );
    }

    #[test]
    fn test_category_to_type() {
        assert_eq!(
            IssueCreator::category_to_type(FindingCategory::Security),
            IssueType::Bug
        );
        assert_eq!(
            IssueCreator::category_to_type(FindingCategory::Documentation),
            IssueType::Documentation
        );
        assert_eq!(
            IssueCreator::category_to_type(FindingCategory::TechDebt),
            IssueType::TechDebt
        );
    }

    #[test]
    fn test_estimate_size() {
        let mut finding = test_finding(FindingPriority::P1, FindingCategory::Security);
        assert_eq!(IssueCreator::estimate_size(&finding), IssueSize::XS);
        for (n, expected) in [
            (3, IssueSize::S),
            (5, IssueSize::M),
            (8, IssueSize::L),
            (15, IssueSize::XL),
        ] {
            finding.affected_files = (0..n)
                .map(|i| AffectedFile::new(format!("{i}.rs")))
                .collect();
            assert_eq!(IssueCreator::estimate_size(&finding), expected);
        }
    }

    #[tokio::test]
    async fn test_priority_filter_and_dedup_in_dry_run() {
        let mut creator = IssueCreator::new("owner/repo")
            .with_min_priority(FindingPriority::P1)
            .with_dry_run(true);
        let low = test_finding(FindingPriority::P3, FindingCategory::Quality);
        let high = test_finding(FindingPriority::P0, FindingCategory::Security);

        let r = creator.process_finding(low).await;
        assert!(r.skipped_reason.unwrap().contains("below min priority"));

        let r = creator.process_finding(high.clone()).await;
        assert_eq!(r.skipped_reason.as_deref(), Some("dry run mode"));
        let r = creator.process_finding(high).await;
        assert!(r.skipped_reason.unwrap().contains("duplicate"));
    }

    #[test]
    fn test_extract_fingerprint() {
        assert_eq!(
            extract_fingerprint("x\n<!-- analysis-fingerprint:abc123 -->\n"),
            Some("abc123".to_string())
        );
        assert_eq!(
            extract_fingerprint("<!-- analysis-fingerprint:not hex -->"),
            None
        );
        assert_eq!(extract_fingerprint("nothing"), None);
    }

    #[test]
    fn test_parse_issue_number() {
        assert_eq!(
            parse_issue_number("https://github.com/o/r/issues/123\n"),
            Some(123)
        );
        assert_eq!(parse_issue_number("https://github.com/o/r/issues/"), None);
        assert_eq!(parse_issue_number("garbage"), None);
    }

    #[test]
    fn test_creation_result_constructors() {
        let finding = test_finding(FindingPriority::P1, FindingCategory::Security);
        let skipped = CreationResult::skipped(finding.clone(), "test reason");
        assert!(!skipped.created);
        let success = CreationResult::success(finding, 123, "https://x/issues/123".to_string());
        assert!(success.created);
        assert_eq!(success.issue_number, Some(123));
    }
}
