//! Base analyzer types for codebase analysis agents.
//!
//! This module provides the foundation for specialized analyzers that inspect
//! the codebase and generate findings for automated issue creation.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tracing::{debug, info, warn};

use crate::agents::{Agent, AgentContext};
use crate::error::Error;

/// Categories of analysis findings.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FindingCategory {
    Security,
    Performance,
    Quality,
    TechDebt,
    Documentation,
    Testing,
    Architecture,
    Dependency,
}

impl FindingCategory {
    /// Get all categories.
    pub fn all() -> Vec<FindingCategory> {
        vec![
            FindingCategory::Security,
            FindingCategory::Performance,
            FindingCategory::Quality,
            FindingCategory::TechDebt,
            FindingCategory::Documentation,
            FindingCategory::Testing,
            FindingCategory::Architecture,
            FindingCategory::Dependency,
        ]
    }

    /// Get the string value of the category.
    pub fn value(&self) -> &'static str {
        match self {
            FindingCategory::Security => "security",
            FindingCategory::Performance => "performance",
            FindingCategory::Quality => "quality",
            FindingCategory::TechDebt => "tech_debt",
            FindingCategory::Documentation => "documentation",
            FindingCategory::Testing => "testing",
            FindingCategory::Architecture => "architecture",
            FindingCategory::Dependency => "dependency",
        }
    }

    /// Get the title-case display name.
    pub fn display(&self) -> &'static str {
        match self {
            FindingCategory::Security => "Security",
            FindingCategory::Performance => "Performance",
            FindingCategory::Quality => "Quality",
            FindingCategory::TechDebt => "Tech Debt",
            FindingCategory::Documentation => "Documentation",
            FindingCategory::Testing => "Testing",
            FindingCategory::Architecture => "Architecture",
            FindingCategory::Dependency => "Dependency",
        }
    }

    /// Parse from string.
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "security" => Some(FindingCategory::Security),
            "performance" => Some(FindingCategory::Performance),
            "quality" => Some(FindingCategory::Quality),
            "tech_debt" | "techdebt" => Some(FindingCategory::TechDebt),
            "documentation" | "docs" => Some(FindingCategory::Documentation),
            "testing" | "test" => Some(FindingCategory::Testing),
            "architecture" | "arch" => Some(FindingCategory::Architecture),
            "dependency" | "deps" => Some(FindingCategory::Dependency),
            _ => None,
        }
    }
}

/// Priority levels for findings.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum FindingPriority {
    /// Critical - Security vulnerabilities, data loss risks
    P0,
    /// High - Bugs, performance issues
    P1,
    /// Medium - Code quality, tech debt
    P2,
    /// Low - Nice to have, minor improvements
    P3,
}

impl FindingPriority {
    /// Get all priorities in order (P0 first).
    pub fn all() -> Vec<FindingPriority> {
        vec![
            FindingPriority::P0,
            FindingPriority::P1,
            FindingPriority::P2,
            FindingPriority::P3,
        ]
    }

    /// Get the string value.
    pub fn value(&self) -> &'static str {
        match self {
            FindingPriority::P0 => "P0",
            FindingPriority::P1 => "P1",
            FindingPriority::P2 => "P2",
            FindingPriority::P3 => "P3",
        }
    }

    /// Parse from string.
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_uppercase().as_str() {
            "P0" => Some(FindingPriority::P0),
            "P1" => Some(FindingPriority::P1),
            "P2" => Some(FindingPriority::P2),
            "P3" => Some(FindingPriority::P3),
            _ => None,
        }
    }

    /// Get the numeric index (0 for P0, 3 for P3).
    pub fn index(&self) -> usize {
        match self {
            FindingPriority::P0 => 0,
            FindingPriority::P1 => 1,
            FindingPriority::P2 => 2,
            FindingPriority::P3 => 3,
        }
    }
}

/// Represents a file affected by a finding.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AffectedFile {
    /// File path relative to repository root.
    pub path: String,
    /// Optional start line number.
    pub line_start: Option<u32>,
    /// Optional end line number.
    pub line_end: Option<u32>,
    /// Optional code snippet.
    pub snippet: Option<String>,
}

impl AffectedFile {
    /// Create a new affected file.
    pub fn new(path: impl Into<String>) -> Self {
        Self {
            path: path.into(),
            line_start: None,
            line_end: None,
            snippet: None,
        }
    }

    /// Create with line range.
    pub fn with_lines(path: impl Into<String>, start: u32, end: Option<u32>) -> Self {
        Self {
            path: path.into(),
            line_start: Some(start),
            line_end: end,
            snippet: None,
        }
    }

    /// Generate a file reference string.
    pub fn to_reference(&self) -> String {
        if let (Some(start), Some(end)) = (self.line_start, self.line_end) {
            format!("`{}:L{}-L{}`", self.path, start, end)
        } else if let Some(start) = self.line_start {
            format!("`{}:L{}`", self.path, start)
        } else {
            format!("`{}`", self.path)
        }
    }
}

/// Effort estimate for a finding.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EffortEstimate {
    XS,
    S,
    M,
    L,
    XL,
}

impl Default for EffortEstimate {
    fn default() -> Self {
        EffortEstimate::M
    }
}

impl EffortEstimate {
    /// Get the string value.
    pub fn value(&self) -> &'static str {
        match self {
            EffortEstimate::XS => "XS",
            EffortEstimate::S => "S",
            EffortEstimate::M => "M",
            EffortEstimate::L => "L",
            EffortEstimate::XL => "XL",
        }
    }
}

/// Represents a single finding from codebase analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisFinding {
    /// Brief title.
    pub title: String,
    /// 1-2 sentence summary.
    pub summary: String,
    /// Full explanation.
    pub details: String,
    /// Finding category.
    pub category: FindingCategory,
    /// Priority level.
    pub priority: FindingPriority,
    /// Affected files with optional line ranges.
    pub affected_files: Vec<AffectedFile>,
    /// Suggested fix approach.
    pub suggested_fix: String,
    /// Supporting evidence (code or metrics).
    pub evidence: String,
    /// Agent that discovered this finding.
    pub discovered_by: String,
    /// When the analysis was run.
    #[serde(default = "Utc::now")]
    pub analysis_date: DateTime<Utc>,
    /// Effort estimate.
    #[serde(default)]
    pub effort_estimate: EffortEstimate,
    /// Additional tags.
    #[serde(default)]
    pub tags: Vec<String>,
    /// Arbitrary metadata.
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

impl AnalysisFinding {
    /// Generate a unique fingerprint for deduplication.
    ///
    /// The fingerprint is based on category, affected files, and key content
    /// to identify conceptually similar findings across runs.
    pub fn fingerprint(&self) -> String {
        let first_file = self.affected_files.first();
        let file_path = first_file.map(|f| f.path.as_str()).unwrap_or("");
        let line_start = first_file
            .and_then(|f| f.line_start)
            .map(|l| l.to_string())
            .unwrap_or_default();

        // Get first 5 words of title, sorted and lowercased
        let mut title_words: Vec<_> = self
            .title
            .to_lowercase()
            .split_whitespace()
            .take(5)
            .map(String::from)
            .collect();
        title_words.sort();
        let title_key = title_words.join(" ");

        let components = format!(
            "{}|{}|{}|{}|{}",
            self.category.value(),
            self.priority.value(),
            file_path,
            line_start,
            title_key
        );

        let mut hasher = Sha256::new();
        hasher.update(components.as_bytes());
        let result = hasher.finalize();
        hex::encode(&result[..8]) // First 16 hex chars (8 bytes)
    }

    /// Generate GitHub issue body markdown.
    pub fn to_issue_body(&self) -> String {
        let affected_refs: Vec<_> = self
            .affected_files
            .iter()
            .map(|af| format!("- {}", af.to_reference()))
            .collect();
        let affected_section = affected_refs.join("\n");

        let evidence_section = if !self.evidence.is_empty() {
            format!("### Evidence\n{}\n\n", self.evidence)
        } else {
            String::new()
        };

        format!(
            r#"> [!IMPORTANT]
> **This issue is reserved for AI agents.** It was automatically generated by
> the codebase analysis pipeline and will be implemented by an AI agent upon
> approval. **Public contributors: please do not work on this issue.**

---

## [{}]: {}

**Category**: {}
**Priority**: {}
**Effort Estimate**: {}
**Discovered By**: {}
**Analysis Run**: {}

### Summary
{}

### Details
{}

### Affected Files
{}

### Suggested Fix
{}

{}---
*Generated by Codebase Analysis Pipeline*
*Awaiting admin review - reply with `[Approved]` to create PR*

<!-- analysis-fingerprint:{} -->
<!-- discovered-by:{} -->"#,
            self.category.display(),
            self.title,
            self.category.display(),
            self.priority.value(),
            self.effort_estimate.value(),
            self.discovered_by,
            self.analysis_date.format("%Y-%m-%d"),
            self.summary,
            self.details,
            affected_section,
            self.suggested_fix,
            evidence_section,
            self.fingerprint(),
            self.discovered_by,
        )
    }

    /// Generate GitHub issue title.
    pub fn to_issue_title(&self) -> String {
        format!("[{}] {}", self.category.display(), self.title)
    }
}

/// Base trait for codebase analyzers.
///
/// Subclasses implement specific analysis logic for different concerns
/// (security, performance, architecture, etc.).
#[async_trait]
pub trait BaseAnalyzer: Send + Sync {
    /// Human-readable description of what this analyzer focuses on.
    fn analysis_focus(&self) -> &str;

    /// List of finding categories this analyzer can produce.
    fn supported_categories(&self) -> &[FindingCategory];

    /// Perform analysis on the repository.
    async fn analyze(&mut self, repo_path: &Path) -> Result<Vec<AnalysisFinding>, Error>;

    /// Get the agent name.
    fn agent_name(&self) -> &str;
}

/// Analyzer that delegates to an AI agent for analysis.
///
/// This wraps an existing agent (Claude, Gemini, Codex, etc.) and
/// prompts it to analyze specific aspects of the codebase.
pub struct AgentAnalyzer {
    agent_name: String,
    agent: Arc<dyn Agent>,
    analysis_prompt: String,
    categories: Vec<FindingCategory>,
    include_paths: Vec<String>,
    exclude_paths: Vec<String>,
    findings: Vec<AnalysisFinding>,
}

// Token/character limits for file content
const MAX_FILES_TO_READ: usize = 20;
const MAX_CHARS_PER_FILE: usize = 3000;
const MAX_TOTAL_CHARS: usize = 50000;

impl AgentAnalyzer {
    /// Create a new agent-based analyzer.
    pub fn new(
        agent_name: impl Into<String>,
        agent: Arc<dyn Agent>,
        analysis_prompt: impl Into<String>,
        categories: Vec<FindingCategory>,
    ) -> Self {
        Self {
            agent_name: agent_name.into(),
            agent,
            analysis_prompt: analysis_prompt.into(),
            categories,
            include_paths: vec!["**/*.py".to_string()],
            exclude_paths: vec![
                "**/tests/**".to_string(),
                "**/__pycache__/**".to_string(),
                "**/node_modules/**".to_string(),
                "**/.git/**".to_string(),
            ],
            findings: Vec::new(),
        }
    }

    /// Set include path patterns.
    pub fn with_include_paths(mut self, paths: Vec<String>) -> Self {
        self.include_paths = paths;
        self
    }

    /// Set exclude path patterns.
    pub fn with_exclude_paths(mut self, paths: Vec<String>) -> Self {
        self.exclude_paths = paths;
        self
    }

    /// Check if a file should be included in analysis.
    fn should_include_file(&self, file_path: &Path, repo_root: &Path) -> bool {
        let relative = match file_path.strip_prefix(repo_root) {
            Ok(r) => r,
            Err(_) => return false,
        };
        let relative_str = relative.to_string_lossy();

        // Check exclusions first
        for pattern in &self.exclude_paths {
            if Self::matches_glob(pattern, &relative_str) {
                return false;
            }
        }

        // Check inclusions
        for pattern in &self.include_paths {
            if Self::matches_glob(pattern, &relative_str) {
                return true;
            }
        }

        false
    }

    /// Simple glob matching (supports * and **).
    fn matches_glob(pattern: &str, path: &str) -> bool {
        // Convert glob to regex
        let regex_pattern = pattern
            .replace(".", r"\.")
            .replace("**", "{{DOUBLESTAR}}")
            .replace("*", "[^/]*")
            .replace("{{DOUBLESTAR}}", ".*");

        if let Ok(re) = Regex::new(&format!("^{}$", regex_pattern)) {
            re.is_match(path)
        } else {
            false
        }
    }

    /// Collect all files to analyze.
    fn collect_files(&self, repo_path: &Path) -> Vec<PathBuf> {
        let mut files = Vec::new();
        let mut seen = std::collections::HashSet::new();

        for pattern in &self.include_paths {
            // Walk directory and check against pattern
            if let Ok(entries) = std::fs::read_dir(repo_path) {
                self.collect_files_recursive(repo_path, repo_path, pattern, &mut files, &mut seen);
            }
        }

        files.sort();
        files
    }

    fn collect_files_recursive(
        &self,
        current: &Path,
        repo_root: &Path,
        _pattern: &str,
        files: &mut Vec<PathBuf>,
        seen: &mut std::collections::HashSet<PathBuf>,
    ) {
        if let Ok(entries) = std::fs::read_dir(current) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    self.collect_files_recursive(&path, repo_root, _pattern, files, seen);
                } else if path.is_file() && !seen.contains(&path) {
                    if self.should_include_file(&path, repo_root) {
                        files.push(path.clone());
                        seen.insert(path);
                    }
                }
            }
        }
    }

    /// Read file contents with character limits.
    fn read_file_contents(&self, files: &[PathBuf], repo_path: &Path) -> String {
        let mut contents = Vec::new();
        let mut total_chars = 0;

        for file_path in files.iter().take(MAX_FILES_TO_READ) {
            if total_chars >= MAX_TOTAL_CHARS {
                contents.push(format!(
                    "\n... truncated (reached {} char limit)",
                    MAX_TOTAL_CHARS
                ));
                break;
            }

            let relative_path = file_path
                .strip_prefix(repo_path)
                .unwrap_or(file_path)
                .to_string_lossy();

            match std::fs::read_to_string(file_path) {
                Ok(mut content) => {
                    // Truncate if too long
                    if content.len() > MAX_CHARS_PER_FILE {
                        content.truncate(MAX_CHARS_PER_FILE);
                        content.push_str(&format!(
                            "\n... (truncated at {} chars)",
                            MAX_CHARS_PER_FILE
                        ));
                    }

                    // Check total limit
                    if total_chars + content.len() > MAX_TOTAL_CHARS {
                        let remaining = MAX_TOTAL_CHARS - total_chars;
                        content.truncate(remaining);
                        content.push_str("\n... (truncated due to total limit)");
                    }

                    total_chars += content.len();
                    contents.push(format!("### {}\n```\n{}\n```", relative_path, content));
                }
                Err(e) => {
                    warn!("Failed to read {}: {}", file_path.display(), e);
                    contents.push(format!("### {}\n(could not read: {})", relative_path, e));
                }
            }
        }

        contents.join("\n\n")
    }

    /// Parse agent response into findings.
    fn parse_agent_response(&self, response: &str) -> Vec<AnalysisFinding> {
        // First try to parse as JSON (preferred format)
        if let Some(findings) = self.parse_json_response(response) {
            return findings;
        }

        // Fallback to text-based parsing
        debug!("JSON parsing failed, trying text-based parsing");
        let mut findings = Vec::new();

        // Split response by separator
        let section_re = Regex::new(r"\n---+\n").unwrap();
        let sections: Vec<_> = section_re.split(response).collect();

        for section in sections {
            let section = section.trim();
            if section.is_empty() || section.len() < 50 {
                continue;
            }

            match self.parse_single_finding(section) {
                Some(finding) => findings.push(finding),
                None => {
                    debug!("Failed to parse finding section");
                }
            }
        }

        debug!(
            "Parsed {} findings from {} chars",
            findings.len(),
            response.len()
        );
        findings
    }

    /// Parse JSON response into findings.
    fn parse_json_response(&self, response: &str) -> Option<Vec<AnalysisFinding>> {
        // Try to extract JSON array from response
        // It may be wrapped in markdown code blocks or have extra text
        let json_str = Self::extract_json_array(response)?;

        #[derive(Deserialize)]
        struct RawFinding {
            title: String,
            category: Option<String>,
            priority: Option<String>,
            summary: Option<String>,
            details: Option<String>,
            files: Option<Vec<RawFile>>,
            fix: Option<String>,
            evidence: Option<String>,
        }

        #[derive(Deserialize)]
        struct RawFile {
            path: String,
            line_start: Option<u32>,
            line_end: Option<u32>,
        }

        let raw_findings: Vec<RawFinding> = match serde_json::from_str(&json_str) {
            Ok(f) => f,
            Err(e) => {
                debug!("JSON parse error: {}", e);
                return None;
            }
        };

        let mut findings = Vec::new();
        for raw in raw_findings {
            let category = raw
                .category
                .as_ref()
                .and_then(|c| FindingCategory::from_str(c))
                .unwrap_or(FindingCategory::Quality);

            let priority = raw
                .priority
                .as_ref()
                .and_then(|p| FindingPriority::from_str(p))
                .unwrap_or(FindingPriority::P2);

            let affected_files: Vec<AffectedFile> = raw
                .files
                .unwrap_or_default()
                .into_iter()
                .map(|f| AffectedFile {
                    path: f.path,
                    line_start: f.line_start,
                    line_end: f.line_end,
                    snippet: None,
                })
                .collect();

            let affected_files = if affected_files.is_empty() {
                vec![AffectedFile::new("(unknown)")]
            } else {
                affected_files
            };

            let summary = raw.summary.unwrap_or_default();
            let details = raw.details.unwrap_or_default();

            // Skip if no meaningful content
            if raw.title.is_empty() || (summary.is_empty() && details.is_empty()) {
                continue;
            }

            // Handle summary/details with cloning to avoid move issues
            let final_summary = if summary.is_empty() {
                details.chars().take(200).collect()
            } else {
                summary.clone()
            };
            let final_details = if details.is_empty() {
                summary
            } else {
                details
            };

            findings.push(AnalysisFinding {
                title: raw.title,
                summary: final_summary,
                details: final_details,
                category,
                priority,
                affected_files,
                suggested_fix: raw.fix.unwrap_or_else(|| "See details for recommendations".to_string()),
                evidence: raw.evidence.unwrap_or_default(),
                discovered_by: self.agent_name.clone(),
                analysis_date: Utc::now(),
                effort_estimate: EffortEstimate::M,
                tags: Vec::new(),
                metadata: HashMap::new(),
            });
        }

        info!("Parsed {} findings from JSON response", findings.len());
        Some(findings)
    }

    /// Extract JSON array from response text (may be wrapped in markdown or have extra text).
    fn extract_json_array(response: &str) -> Option<String> {
        // Try to find JSON array in the response
        // First, try to extract from markdown code block
        let code_block_re = Regex::new(r"```(?:json)?\s*\n?([\s\S]*?)\n?```").ok()?;
        if let Some(cap) = code_block_re.captures(response) {
            let content = cap.get(1)?.as_str().trim();
            if content.starts_with('[') {
                return Some(content.to_string());
            }
        }

        // Try to find raw JSON array
        let response = response.trim();
        if response.starts_with('[') {
            // Find matching closing bracket
            let mut depth = 0;
            let mut end = 0;
            for (i, c) in response.char_indices() {
                match c {
                    '[' => depth += 1,
                    ']' => {
                        depth -= 1;
                        if depth == 0 {
                            end = i + 1;
                            break;
                        }
                    }
                    _ => {}
                }
            }
            if end > 0 {
                return Some(response[..end].to_string());
            }
        }

        // Try to find JSON array anywhere in the response
        if let Some(start) = response.find('[') {
            let rest = &response[start..];
            let mut depth = 0;
            let mut end = 0;
            for (i, c) in rest.char_indices() {
                match c {
                    '[' => depth += 1,
                    ']' => {
                        depth -= 1;
                        if depth == 0 {
                            end = i + 1;
                            break;
                        }
                    }
                    _ => {}
                }
            }
            if end > 0 {
                return Some(rest[..end].to_string());
            }
        }

        None
    }

    /// Parse a single finding from a section of agent response.
    fn parse_single_finding(&self, section: &str) -> Option<AnalysisFinding> {
        // Helper to extract field
        fn extract_field(pattern: &str, text: &str) -> Option<String> {
            let re = Regex::new(pattern).ok()?;
            re.captures(text)
                .and_then(|c| c.get(1))
                .map(|m| m.as_str().trim().to_string())
        }

        let title = extract_field(r"(?i)TITLE:\s*(.+?)(?:\n|$)", section)
            .or_else(|| extract_field(r"^#+\s*(.+?)$", section))
            .filter(|t| !t.is_empty())?;

        let category_str = extract_field(r"(?i)CATEGORY:\s*(\w+)", section)
            .unwrap_or_else(|| "quality".to_string());
        let priority_str =
            extract_field(r"(?i)PRIORITY:\s*(P\d)", section).unwrap_or_else(|| "P2".to_string());
        let summary =
            extract_field(r"(?i)SUMMARY:\s*(.+?)(?:\n\n|\nDETAILS:)", section).unwrap_or_default();
        let details =
            extract_field(r"(?i)DETAILS:\s*(.+?)(?:\n\n|\nFILES:)", section).unwrap_or_default();
        let files_str =
            extract_field(r"(?i)FILES:\s*(.+?)(?:\n\n|\nFIX:)", section).unwrap_or_default();
        let fix = extract_field(r"(?i)FIX:\s*(.+?)(?:\n\n|\nEVIDENCE:|$)", section)
            .unwrap_or_else(|| "See details for recommendations".to_string());
        let evidence = extract_field(r"(?i)EVIDENCE:\s*(.+?)$", section).unwrap_or_default();

        // Parse category
        let category = FindingCategory::from_str(&category_str).unwrap_or(FindingCategory::Quality);

        // Parse priority
        let priority = FindingPriority::from_str(&priority_str).unwrap_or(FindingPriority::P2);

        // Parse affected files
        let mut affected_files = Vec::new();
        let file_re = Regex::new(r"`?([^`\n]+?\.\w+)(?::L?(\d+))?(?:-L?(\d+))?`?").ok()?;
        for cap in file_re.captures_iter(&files_str) {
            let path = cap.get(1)?.as_str().to_string();
            let line_start = cap.get(2).and_then(|m| m.as_str().parse().ok());
            let line_end = cap.get(3).and_then(|m| m.as_str().parse().ok());
            affected_files.push(AffectedFile {
                path,
                line_start,
                line_end,
                snippet: None,
            });
        }

        if affected_files.is_empty() {
            affected_files.push(AffectedFile::new("(unknown)"));
        }

        if title.is_empty() || (summary.is_empty() && details.is_empty()) {
            return None;
        }

        // Handle summary/details with proper cloning to avoid move issues
        let (final_summary, final_details) = if summary.is_empty() && !details.is_empty() {
            (details.chars().take(200).collect(), details)
        } else if details.is_empty() && !summary.is_empty() {
            (summary.clone(), summary)
        } else {
            (summary, details)
        };

        Some(AnalysisFinding {
            title,
            summary: final_summary,
            details: final_details,
            category,
            priority,
            affected_files,
            suggested_fix: fix,
            evidence,
            discovered_by: self.agent_name.clone(),
            analysis_date: Utc::now(),
            effort_estimate: EffortEstimate::M,
            tags: Vec::new(),
            metadata: HashMap::new(),
        })
    }

    /// Add a finding to the results.
    pub fn add_finding(&mut self, finding: AnalysisFinding) {
        info!("[{}] {}", finding.priority.value(), finding.title);
        self.findings.push(finding);
    }

    /// Clear all findings.
    pub fn clear_findings(&mut self) {
        self.findings.clear();
    }

    /// Get all findings.
    pub fn findings(&self) -> &[AnalysisFinding] {
        &self.findings
    }
}

#[async_trait]
impl BaseAnalyzer for AgentAnalyzer {
    fn analysis_focus(&self) -> &str {
        "AI-powered codebase analysis"
    }

    fn supported_categories(&self) -> &[FindingCategory] {
        &self.categories
    }

    fn agent_name(&self) -> &str {
        &self.agent_name
    }

    async fn analyze(&mut self, repo_path: &Path) -> Result<Vec<AnalysisFinding>, Error> {
        self.clear_findings();
        let files = self.collect_files(repo_path);

        if files.is_empty() {
            warn!("No files found for analysis in {}", repo_path.display());
            return Ok(Vec::new());
        }

        // Build file content for the agent (with limits to prevent token overflow)
        let file_contents =
            self.read_file_contents(&files[..files.len().min(MAX_FILES_TO_READ)], repo_path);

        // List remaining files (paths only) if we couldn't read all
        let remaining_files = if files.len() > MAX_FILES_TO_READ {
            &files[MAX_FILES_TO_READ..]
        } else {
            &[]
        };

        let mut remaining_list = String::new();
        if !remaining_files.is_empty() {
            remaining_list
                .push_str("\n\n## Additional Files (paths only, not included in analysis)\n");
            for (i, f) in remaining_files.iter().take(30).enumerate() {
                let relative = f.strip_prefix(repo_path).unwrap_or(f);
                remaining_list.push_str(&format!("- {}\n", relative.display()));
                if i == 29 && remaining_files.len() > 30 {
                    remaining_list.push_str(&format!(
                        "... and {} more files\n",
                        remaining_files.len() - 30
                    ));
                }
            }
        }

        let categories_str = self
            .categories
            .iter()
            .map(|c| c.value())
            .collect::<Vec<_>>()
            .join(", ");

        let prompt = format!(
            r#"{}

## Files to Analyze

{}{}

## Output Format (IMPORTANT)
You MUST output your findings as a JSON array. Each finding must be a JSON object with these fields:
- "title": string - Brief descriptive title
- "category": string - One of: {}
- "priority": string - "P0" (critical), "P1" (high), "P2" (medium), or "P3" (low)
- "summary": string - 1-2 sentence description
- "details": string - Full explanation of the issue
- "files": array of objects with "path" (string), "line_start" (number or null), "line_end" (number or null)
- "fix": string - Suggested fix approach
- "evidence": string - Supporting code snippets or metrics

Output ONLY the JSON array, starting with [ and ending with ].
Do not include any text before or after the JSON.
If you find no issues, return an empty array: []

Example output:
```json
[
  {{
    "title": "SQL Injection Risk",
    "category": "security",
    "priority": "P1",
    "summary": "User input is directly interpolated into SQL query.",
    "details": "The function uses string formatting to build SQL queries...",
    "files": [{{"path": "src/db.py", "line_start": 42, "line_end": 45}}],
    "fix": "Use parameterized queries or an ORM.",
    "evidence": "sql = f'SELECT * FROM users WHERE id = {{user_id}}'"
  }}
]
```"#,
            self.analysis_prompt, file_contents, remaining_list, categories_str
        );

        // Execute agent
        let mut context = AgentContext::new();
        context.mode = Some("analysis".to_string());
        context.repo_path = Some(repo_path.to_string_lossy().to_string());
        context
            .extra
            .insert("file_count".to_string(), serde_json::json!(files.len()));
        context.extra.insert(
            "files_with_content".to_string(),
            serde_json::json!(files.len().min(MAX_FILES_TO_READ)),
        );

        match self.agent.generate_code(&prompt, &context).await {
            Ok(response) => {
                let findings = self.parse_agent_response(&response);
                for finding in findings {
                    self.add_finding(finding);
                }
            }
            Err(e) => {
                warn!("Agent analysis failed: {}", e);
            }
        }

        Ok(self.findings.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_finding_category_values() {
        assert_eq!(FindingCategory::Security.value(), "security");
        assert_eq!(FindingCategory::TechDebt.value(), "tech_debt");
        assert_eq!(FindingCategory::TechDebt.display(), "Tech Debt");
    }

    #[test]
    fn test_finding_category_from_str() {
        assert_eq!(
            FindingCategory::from_str("security"),
            Some(FindingCategory::Security)
        );
        assert_eq!(
            FindingCategory::from_str("SECURITY"),
            Some(FindingCategory::Security)
        );
        assert_eq!(
            FindingCategory::from_str("tech_debt"),
            Some(FindingCategory::TechDebt)
        );
        assert_eq!(
            FindingCategory::from_str("techdebt"),
            Some(FindingCategory::TechDebt)
        );
        assert_eq!(FindingCategory::from_str("invalid"), None);
    }

    #[test]
    fn test_finding_priority_order() {
        assert!(FindingPriority::P0 < FindingPriority::P1);
        assert!(FindingPriority::P1 < FindingPriority::P2);
        assert!(FindingPriority::P2 < FindingPriority::P3);
    }

    #[test]
    fn test_finding_priority_from_str() {
        assert_eq!(FindingPriority::from_str("P0"), Some(FindingPriority::P0));
        assert_eq!(FindingPriority::from_str("p1"), Some(FindingPriority::P1));
        assert_eq!(FindingPriority::from_str("invalid"), None);
    }

    #[test]
    fn test_affected_file_reference() {
        let af = AffectedFile::new("src/main.rs");
        assert_eq!(af.to_reference(), "`src/main.rs`");

        let af_with_start = AffectedFile::with_lines("src/main.rs", 10, None);
        assert_eq!(af_with_start.to_reference(), "`src/main.rs:L10`");

        let af_with_range = AffectedFile::with_lines("src/main.rs", 10, Some(20));
        assert_eq!(af_with_range.to_reference(), "`src/main.rs:L10-L20`");
    }

    #[test]
    fn test_finding_fingerprint() {
        let finding = AnalysisFinding {
            title: "Test Finding".to_string(),
            summary: "A test summary".to_string(),
            details: "Test details".to_string(),
            category: FindingCategory::Security,
            priority: FindingPriority::P1,
            affected_files: vec![AffectedFile::with_lines("src/main.rs", 10, Some(20))],
            suggested_fix: "Fix it".to_string(),
            evidence: "Evidence".to_string(),
            discovered_by: "TestAgent".to_string(),
            analysis_date: Utc::now(),
            effort_estimate: EffortEstimate::M,
            tags: Vec::new(),
            metadata: HashMap::new(),
        };

        let fp = finding.fingerprint();
        assert_eq!(fp.len(), 16); // 8 bytes = 16 hex chars

        // Same finding should produce same fingerprint
        let fp2 = finding.fingerprint();
        assert_eq!(fp, fp2);
    }

    #[test]
    fn test_finding_to_issue_title() {
        let finding = AnalysisFinding {
            title: "SQL Injection Vulnerability".to_string(),
            summary: "Found SQL injection".to_string(),
            details: "Details".to_string(),
            category: FindingCategory::Security,
            priority: FindingPriority::P0,
            affected_files: vec![AffectedFile::new("src/db.py")],
            suggested_fix: "Use parameterized queries".to_string(),
            evidence: "".to_string(),
            discovered_by: "Claude".to_string(),
            analysis_date: Utc::now(),
            effort_estimate: EffortEstimate::M,
            tags: Vec::new(),
            metadata: HashMap::new(),
        };

        assert_eq!(
            finding.to_issue_title(),
            "[Security] SQL Injection Vulnerability"
        );
    }

    #[test]
    fn test_glob_matching() {
        assert!(AgentAnalyzer::matches_glob("**/*.py", "src/main.py"));
        assert!(AgentAnalyzer::matches_glob(
            "**/*.py",
            "deep/nested/file.py"
        ));
        assert!(!AgentAnalyzer::matches_glob("**/*.py", "src/main.rs"));
        assert!(AgentAnalyzer::matches_glob("*.py", "main.py"));
        assert!(!AgentAnalyzer::matches_glob("*.py", "src/main.py"));
        assert!(AgentAnalyzer::matches_glob(
            "**/tests/**",
            "src/tests/test_main.py"
        ));
    }
}
