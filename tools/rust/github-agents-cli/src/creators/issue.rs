//! Issue creator for automated issue generation from analysis findings.
//!
//! This module handles:
//! - Creating GitHub issues from analysis findings
//! - Deduplication against existing issues
//! - Adding issues to the project board
//! - Tracking creation history for metrics

use std::collections::HashSet;

use chrono::{Duration, Utc};
use serde::{Deserialize, Serialize};
use tracing::{debug, error, info, warn};

use crate::analyzers::{AnalysisFinding, FindingCategory, FindingPriority};
use crate::error::Error;
use crate::utils::{run_gh_command, run_gh_command_with_stderr};

/// Result of issue creation attempt.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreationResult {
    /// The finding that was processed.
    pub finding: AnalysisFinding,
    /// Issue number if created.
    pub issue_number: Option<i64>,
    /// Issue URL if created.
    pub issue_url: Option<String>,
    /// Whether the issue was created.
    pub created: bool,
    /// Reason for skipping if not created.
    pub skipped_reason: Option<String>,
    /// Issue number of duplicate if found.
    pub duplicate_of: Option<i64>,
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

    /// Create a duplicate result.
    pub fn duplicate(finding: AnalysisFinding, duplicate_of: i64) -> Self {
        Self {
            finding,
            issue_number: None,
            issue_url: None,
            created: false,
            skipped_reason: Some("semantic duplicate".to_string()),
            duplicate_of: Some(duplicate_of),
        }
    }

    /// Create a success result.
    pub fn success(finding: AnalysisFinding, issue_number: i64, issue_url: String) -> Self {
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
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
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
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IssueType {
    Bug,
    Feature,
    TechDebt,
    Documentation,
}

impl IssueType {
    pub fn value(&self) -> &'static str {
        match self {
            IssueType::Bug => "Bug",
            IssueType::Feature => "Feature",
            IssueType::TechDebt => "Tech Debt",
            IssueType::Documentation => "Documentation",
        }
    }
}

/// Issue priority for board.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
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

/// Creates GitHub issues from analysis findings with deduplication.
///
/// This class handles the full lifecycle of issue creation:
/// 1. Check for duplicates using fingerprints and semantic similarity
/// 2. Create the GitHub issue
/// 3. Apply labels
/// 4. Add to project board (if configured)
/// 5. Store in memory for future deduplication (if configured)
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

    /// Count of issues created this run.
    created_count: usize,
    /// Known fingerprints for deduplication.
    known_fingerprints: HashSet<String>,
    /// Whether labels have been ensured this run.
    labels_ensured: bool,
}

/// Default labels for automated issues.
const DEFAULT_LABELS: &[&str] = &["automated", "needs-review", "agentic-analysis"];

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
            labels_ensured: false,
        }
    }

    /// Set lookback days for duplicate checking.
    pub fn with_lookback_days(mut self, days: i64) -> Self {
        self.lookback_days = days;
        self
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

    /// Get priority label for a finding priority.
    fn priority_label(priority: FindingPriority) -> &'static str {
        match priority {
            FindingPriority::P0 => "priority:critical",
            FindingPriority::P1 => "priority:high",
            FindingPriority::P2 => "priority:medium",
            FindingPriority::P3 => "priority:low",
        }
    }

    /// Map FindingPriority to IssuePriority for board.
    fn priority_to_board(priority: FindingPriority) -> IssuePriority {
        match priority {
            FindingPriority::P0 => IssuePriority::Critical,
            FindingPriority::P1 => IssuePriority::High,
            FindingPriority::P2 => IssuePriority::Medium,
            FindingPriority::P3 => IssuePriority::Low,
        }
    }

    /// Map FindingCategory to IssueType for board.
    fn category_to_type(category: FindingCategory) -> IssueType {
        match category {
            FindingCategory::Security => IssueType::Bug,
            FindingCategory::Performance => IssueType::Bug,
            FindingCategory::Quality => IssueType::TechDebt,
            FindingCategory::TechDebt => IssueType::TechDebt,
            FindingCategory::Documentation => IssueType::Documentation,
            FindingCategory::Testing => IssueType::TechDebt,
            FindingCategory::Architecture => IssueType::TechDebt,
            FindingCategory::Dependency => IssueType::TechDebt,
        }
    }

    /// Estimate issue size based on number of affected files.
    fn estimate_size(finding: &AnalysisFinding) -> IssueSize {
        let num_files = finding.affected_files.len();
        if num_files <= 1 {
            IssueSize::XS
        } else if num_files <= 3 {
            IssueSize::S
        } else if num_files <= 6 {
            IssueSize::M
        } else if num_files <= 10 {
            IssueSize::L
        } else {
            IssueSize::XL
        }
    }

    /// Create GitHub issues from findings.
    pub async fn create_issues(
        &mut self,
        findings: Vec<AnalysisFinding>,
    ) -> Result<Vec<CreationResult>, Error> {
        let mut results = Vec::new();

        // Load known fingerprints from existing issues
        self.load_existing_fingerprints().await;

        // Ensure all required labels exist once per batch (not per issue)
        if !self.labels_ensured && !self.dry_run {
            let mut all_labels: HashSet<String> =
                DEFAULT_LABELS.iter().map(|s| s.to_string()).collect();
            for finding in &findings {
                all_labels.insert(format!("category:{}", finding.category.value()));
                all_labels.insert(Self::priority_label(finding.priority).to_string());
            }
            self.ensure_labels_exist(&all_labels.into_iter().collect::<Vec<_>>())
                .await;
            self.labels_ensured = true;
        }

        // Sort by priority (P0 first)
        let mut sorted_findings = findings;
        sorted_findings.sort_by_key(|f| f.priority.index());

        for finding in sorted_findings {
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
        // Check priority threshold
        if finding.priority.index() > self.min_priority.index() {
            return CreationResult::skipped(
                finding.clone(),
                format!("below min priority ({})", finding.priority.value()),
            );
        }

        // Check fingerprint for exact duplicates
        let fingerprint = finding.fingerprint();
        if self.known_fingerprints.contains(&fingerprint) {
            return CreationResult::skipped(finding, "exact duplicate (fingerprint match)");
        }

        // Create the issue
        if self.dry_run {
            info!("[DRY RUN] Would create issue: {}", finding.to_issue_title());
            return CreationResult::skipped(finding, "dry run mode");
        }

        match self.create_github_issue(&finding).await {
            Ok(result) => {
                if result.created {
                    // Store fingerprint for future dedup
                    self.known_fingerprints.insert(fingerprint);
                }
                result
            },
            Err(e) => {
                error!("Failed to create issue: {}", e);
                CreationResult::skipped(finding, format!("creation failed: {}", e))
            },
        }
    }

    /// Create a GitHub issue for the finding.
    async fn create_github_issue(
        &self,
        finding: &AnalysisFinding,
    ) -> Result<CreationResult, Error> {
        let title = finding.to_issue_title();
        let body = finding.to_issue_body();

        // Build labels
        let labels: Vec<&str> = DEFAULT_LABELS.to_vec();
        let category_label = format!("category:{}", finding.category.value());
        let priority_label = Self::priority_label(finding.priority);

        // We need to convert to String and then join
        let labels_str = format!("{},{},{}", labels.join(","), category_label, priority_label);

        // Create issue via gh CLI
        let args = vec![
            "issue",
            "create",
            "--repo",
            &self.repo,
            "--title",
            &title,
            "--body",
            &body,
            "--label",
            &labels_str,
        ];

        let (stdout, stderr, returncode) = run_gh_command_with_stderr(&args).await?;

        if returncode != 0 {
            let error_msg = stderr
                .or(stdout.clone())
                .unwrap_or_else(|| "unknown error".to_string());
            error!(
                "gh issue create failed (exit {}): {}",
                returncode, error_msg
            );
            return Ok(CreationResult::skipped(
                finding.clone(),
                format!(
                    "gh failed (exit {}): {}",
                    returncode,
                    &error_msg[..error_msg.len().min(100)]
                ),
            ));
        }

        let issue_url = match stdout {
            Some(url) => url,
            None => {
                let error_msg = stderr.unwrap_or_else(|| "no output".to_string());
                error!(
                    "gh issue create returned empty output. stderr: {}",
                    error_msg
                );
                return Ok(CreationResult::skipped(
                    finding.clone(),
                    format!(
                        "gh returned empty output: {}",
                        &error_msg[..error_msg.len().min(100)]
                    ),
                ));
            },
        };

        // Parse issue number from URL
        // gh issue create returns URL like https://github.com/owner/repo/issues/123
        let issue_number = match issue_url.split('/').last() {
            Some(num_str) => match num_str.parse::<i64>() {
                Ok(n) => n,
                Err(e) => {
                    error!(
                        "Failed to parse issue number from output: {:?} - {}",
                        issue_url, e
                    );
                    return Ok(CreationResult::skipped(
                        finding.clone(),
                        format!("failed to parse issue URL: {:?}", issue_url),
                    ));
                },
            },
            None => {
                error!("Failed to parse issue number from output: {:?}", issue_url);
                return Ok(CreationResult::skipped(
                    finding.clone(),
                    format!("failed to parse issue URL: {:?}", issue_url),
                ));
            },
        };

        info!("Created issue #{}: {}", issue_number, title);

        // Add to board via board-manager CLI
        let board_priority = Self::priority_to_board(finding.priority);
        let board_type = Self::category_to_type(finding.category);
        let board_size = Self::estimate_size(finding);

        if let Err(e) = Self::add_to_board(
            issue_number,
            board_priority,
            board_type,
            board_size,
            "Claude Code", // Default agent for codebase analysis
        )
        .await
        {
            warn!("Failed to add issue #{} to board: {}", issue_number, e);
            // Don't fail the whole operation if board addition fails
        }

        Ok(CreationResult::success(
            finding.clone(),
            issue_number,
            issue_url,
        ))
    }

    /// Ensure all required labels exist in the repository.
    async fn ensure_labels_exist(&self, labels: &[String]) {
        // Label colors for different types (without # prefix for API)
        let label_colors: std::collections::HashMap<&str, &str> = [
            ("automated", "0366d6"),              // Blue
            ("needs-review", "fbca04"),           // Yellow
            ("agentic-analysis", "5319e7"),       // Purple
            ("category:security", "d73a4a"),      // Red
            ("category:performance", "a2eeef"),   // Cyan
            ("category:quality", "7057ff"),       // Violet
            ("category:tech_debt", "008672"),     // Teal
            ("category:documentation", "0075ca"), // Blue
            ("category:testing", "bfd4f2"),       // Light blue
            ("category:architecture", "d4c5f9"),  // Light purple
            ("category:dependency", "c5def5"),    // Light blue
            ("priority:critical", "b60205"),      // Dark red
            ("priority:high", "d93f0b"),          // Orange-red
            ("priority:medium", "fbca04"),        // Yellow
            ("priority:low", "0e8a16"),           // Green
        ]
        .into_iter()
        .collect();

        for label in labels {
            // Use gh api to create labels
            let color = label_colors.get(label.as_str()).unwrap_or(&"ededed"); // Default gray

            // Create bindings to extend lifetime of formatted strings
            let repos_path = format!("repos/{}/labels", self.repo);
            let name_field = format!("name={}", label);
            let color_field = format!("color={}", color);

            let args: Vec<&str> = vec![
                "api",
                &repos_path,
                "-X",
                "POST",
                "-f",
                &name_field,
                "-f",
                &color_field,
            ];

            // Don't check result - 422 error means label already exists
            let _ = run_gh_command(&args, false).await;
        }
    }

    /// Load fingerprints from existing issues for deduplication.
    async fn load_existing_fingerprints(&mut self) {
        let cutoff = Utc::now() - Duration::days(self.lookback_days);
        let cutoff_str = cutoff.format("%Y-%m-%d").to_string();
        let search_query = format!("created:>={}", cutoff_str);

        let args: Vec<&str> = vec![
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

        match run_gh_command(&args, false).await {
            Ok(Some(result)) => {
                #[derive(Deserialize)]
                struct IssueData {
                    body: Option<String>,
                }

                match serde_json::from_str::<Vec<IssueData>>(&result) {
                    Ok(issues) => {
                        for issue in issues {
                            if let Some(body) = issue.body {
                                // Extract fingerprint from body
                                if let Some(start) = body.find("analysis-fingerprint:") {
                                    let start = start + "analysis-fingerprint:".len();
                                    if let Some(end) = body[start..].find("-->") {
                                        let fingerprint = body[start..start + end].trim();
                                        self.known_fingerprints.insert(fingerprint.to_string());
                                    }
                                }
                            }
                        }
                        info!(
                            "Loaded {} existing fingerprints",
                            self.known_fingerprints.len()
                        );
                    },
                    Err(e) => {
                        warn!("Failed to parse existing issues: {}", e);
                    },
                }
            },
            Ok(None) => {
                debug!("No existing issues found");
            },
            Err(e) => {
                warn!("Failed to load existing fingerprints: {}", e);
            },
        }
    }

    /// Add an issue to the project board via board-manager CLI.
    ///
    /// This calls the board-manager binary to add the issue with the specified fields.
    /// The board-manager must be available in PATH.
    async fn add_to_board(
        issue_number: i64,
        priority: IssuePriority,
        issue_type: IssueType,
        size: IssueSize,
        agent: &str,
    ) -> Result<(), Error> {
        use std::process::Stdio;
        use tokio::process::Command;

        // Build the board-manager command
        let mut cmd = Command::new("board-manager");
        cmd.arg("add")
            .arg(issue_number.to_string())
            .arg("--priority")
            .arg(priority.value())
            .arg("--type")
            .arg(issue_type.value())
            .arg("--size")
            .arg(size.value())
            .arg("--agent")
            .arg(agent)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        debug!(
            "Running: board-manager add {} --priority {} --type {} --size {} --agent {}",
            issue_number,
            priority.value(),
            issue_type.value(),
            size.value(),
            agent
        );

        let output = cmd.output().await.map_err(|e| {
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
            let stderr = String::from_utf8_lossy(&output.stderr);
            Err(Error::Board(format!(
                "board-manager failed: {}",
                stderr.trim()
            )))
        }
    }

    /// Get the count of issues created this run.
    pub fn created_count(&self) -> usize {
        self.created_count
    }

    /// Reset the creator state for a new run.
    pub fn reset(&mut self) {
        self.created_count = 0;
        self.known_fingerprints.clear();
        self.labels_ensured = false;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::analyzers::AffectedFile;

    fn create_test_finding(
        priority: FindingPriority,
        category: FindingCategory,
    ) -> AnalysisFinding {
        AnalysisFinding {
            title: "Test Finding".to_string(),
            summary: "A test summary".to_string(),
            details: "Test details".to_string(),
            category,
            priority,
            affected_files: vec![AffectedFile::new("src/main.rs")],
            suggested_fix: "Fix it".to_string(),
            evidence: "Evidence".to_string(),
            discovered_by: "TestAgent".to_string(),
            analysis_date: Utc::now(),
            effort_estimate: crate::analyzers::EffortEstimate::M,
            tags: Vec::new(),
            metadata: std::collections::HashMap::new(),
        }
    }

    #[test]
    fn test_priority_label() {
        assert_eq!(
            IssueCreator::priority_label(FindingPriority::P0),
            "priority:critical"
        );
        assert_eq!(
            IssueCreator::priority_label(FindingPriority::P1),
            "priority:high"
        );
        assert_eq!(
            IssueCreator::priority_label(FindingPriority::P2),
            "priority:medium"
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
        let mut finding = create_test_finding(FindingPriority::P1, FindingCategory::Security);

        // 1 file = XS
        assert_eq!(IssueCreator::estimate_size(&finding), IssueSize::XS);

        // 3 files = S
        finding.affected_files = vec![
            AffectedFile::new("a.rs"),
            AffectedFile::new("b.rs"),
            AffectedFile::new("c.rs"),
        ];
        assert_eq!(IssueCreator::estimate_size(&finding), IssueSize::S);

        // 5 files = M
        finding.affected_files = (0..5)
            .map(|i| AffectedFile::new(format!("{}.rs", i)))
            .collect();
        assert_eq!(IssueCreator::estimate_size(&finding), IssueSize::M);

        // 8 files = L
        finding.affected_files = (0..8)
            .map(|i| AffectedFile::new(format!("{}.rs", i)))
            .collect();
        assert_eq!(IssueCreator::estimate_size(&finding), IssueSize::L);

        // 15 files = XL
        finding.affected_files = (0..15)
            .map(|i| AffectedFile::new(format!("{}.rs", i)))
            .collect();
        assert_eq!(IssueCreator::estimate_size(&finding), IssueSize::XL);
    }

    #[test]
    fn test_creation_result_constructors() {
        let finding = create_test_finding(FindingPriority::P1, FindingCategory::Security);

        let skipped = CreationResult::skipped(finding.clone(), "test reason");
        assert!(!skipped.created);
        assert_eq!(skipped.skipped_reason, Some("test reason".to_string()));
        assert!(skipped.issue_number.is_none());

        let duplicate = CreationResult::duplicate(finding.clone(), 42);
        assert!(!duplicate.created);
        assert_eq!(duplicate.duplicate_of, Some(42));

        let success = CreationResult::success(
            finding.clone(),
            123,
            "https://github.com/test/repo/issues/123".to_string(),
        );
        assert!(success.created);
        assert_eq!(success.issue_number, Some(123));
        assert!(success.skipped_reason.is_none());
    }

    #[test]
    fn test_issue_creator_builder() {
        let creator = IssueCreator::new("owner/repo")
            .with_lookback_days(60)
            .with_min_priority(FindingPriority::P2)
            .with_max_issues(10)
            .with_dry_run(true);

        assert_eq!(creator.repo, "owner/repo");
        assert_eq!(creator.lookback_days, 60);
        assert_eq!(creator.min_priority, FindingPriority::P2);
        assert_eq!(creator.max_issues_per_run, 10);
        assert!(creator.dry_run);
    }
}
