//! Agent judgement system for assessing when to auto-fix vs ask for guidance.
//!
//! This module provides intelligent decision-making for AI agents to determine
//! whether they should automatically implement fixes or ask project owners
//! for guidance on uncertain changes.
//!
//! Includes false positive detection to avoid acting on AI reviewer suggestions
//! that contradict observable reality.

use lazy_static::lazy_static;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Categories of fixes with different confidence levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FixCategory {
    // High confidence - always auto-fix
    SecurityVulnerability,
    SyntaxError,
    TypeError,
    ImportError,
    Formatting,
    Linting,
    MissingReturn,
    UnusedImport,
    UnusedVariable,

    // Medium confidence - auto-fix with caution
    ErrorHandling,
    NullCheck,
    EdgeCase,
    Performance,
    Documentation,
    TestCoverage,

    // Low confidence - ask owner
    Architectural,
    ApiChange,
    BreakingChange,
    DataModel,
    BusinessLogic,
    DependencyUpdate,
    MultipleApproaches,

    // Unknown - analyze further or ask
    Unknown,

    // False positive - dismiss silently (AI reviewer was wrong)
    FalsePositive,
}

impl std::fmt::Display for FixCategory {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FixCategory::SecurityVulnerability => write!(f, "security_vulnerability"),
            FixCategory::SyntaxError => write!(f, "syntax_error"),
            FixCategory::TypeError => write!(f, "type_error"),
            FixCategory::ImportError => write!(f, "import_error"),
            FixCategory::Formatting => write!(f, "formatting"),
            FixCategory::Linting => write!(f, "linting"),
            FixCategory::MissingReturn => write!(f, "missing_return"),
            FixCategory::UnusedImport => write!(f, "unused_import"),
            FixCategory::UnusedVariable => write!(f, "unused_variable"),
            FixCategory::ErrorHandling => write!(f, "error_handling"),
            FixCategory::NullCheck => write!(f, "null_check"),
            FixCategory::EdgeCase => write!(f, "edge_case"),
            FixCategory::Performance => write!(f, "performance"),
            FixCategory::Documentation => write!(f, "documentation"),
            FixCategory::TestCoverage => write!(f, "test_coverage"),
            FixCategory::Architectural => write!(f, "architectural"),
            FixCategory::ApiChange => write!(f, "api_change"),
            FixCategory::BreakingChange => write!(f, "breaking_change"),
            FixCategory::DataModel => write!(f, "data_model"),
            FixCategory::BusinessLogic => write!(f, "business_logic"),
            FixCategory::DependencyUpdate => write!(f, "dependency_update"),
            FixCategory::MultipleApproaches => write!(f, "multiple_approaches"),
            FixCategory::Unknown => write!(f, "unknown"),
            FixCategory::FalsePositive => write!(f, "false_positive"),
        }
    }
}

/// Result of agent judgement assessment.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JudgementResult {
    pub should_auto_fix: bool,
    pub confidence: f64,
    pub category: FixCategory,
    pub reasoning: String,
    pub ask_owner_question: Option<String>,
    pub is_false_positive: bool,
    pub dismiss_reason: Option<String>,
}

/// Context for assessing a fix.
#[derive(Debug, Clone, Default)]
pub struct AssessmentContext {
    pub file_path: Option<String>,
    pub diff: Option<String>,
    pub pr_title: Option<String>,
    pub is_security_related: bool,
    pub is_draft_pr: bool,
    pub touches_api: bool,
    pub touches_database: bool,
    pub existing_tests: bool,
    pub pipeline_status: Option<String>,
    pub job_results: HashMap<String, String>,
    pub recent_commits: Vec<String>,
}

lazy_static! {
    // High confidence patterns
    static ref SECURITY_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)sql\s*injection").unwrap(),
        Regex::new(r"(?i)xss\s*(vulnerability)?").unwrap(),
        Regex::new(r"(?i)command\s*injection").unwrap(),
        Regex::new(r"(?i)path\s*traversal").unwrap(),
        Regex::new(r"(?i)insecure\s*(?:random|hash|password)").unwrap(),
        Regex::new(r"(?i)hardcoded\s*(?:password|secret|key|credential)").unwrap(),
        Regex::new(r"(?i)sensitive\s*data\s*(?:exposed|leak)").unwrap(),
        Regex::new(r"(?i)authentication\s*bypass").unwrap(),
        Regex::new(r"(?i)authorization\s*(?:issue|bypass|flaw)").unwrap(),
    ];

    static ref SYNTAX_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)syntax\s*error").unwrap(),
        Regex::new(r"(?i)invalid\s*syntax").unwrap(),
        Regex::new(r"(?i)unexpected\s*token").unwrap(),
        Regex::new(r"(?i)missing\s*(?:bracket|parenthesis|colon|semicolon)").unwrap(),
    ];

    static ref TYPE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)type\s*error").unwrap(),
        Regex::new(r"(?i)type\s*mismatch").unwrap(),
        Regex::new(r"(?i)incompatible\s*type").unwrap(),
        Regex::new(r"(?i)wrong\s*type").unwrap(),
        Regex::new(r"(?i)expected\s*\w+\s*(?:but\s*)?got\s*\w+").unwrap(),
    ];

    static ref IMPORT_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)import\s*error").unwrap(),
        Regex::new(r"(?i)module\s*not\s*found").unwrap(),
        Regex::new(r"(?i)cannot\s*(?:find|import)\s*module").unwrap(),
        Regex::new(r"(?i)unresolved\s*(?:import|reference)").unwrap(),
    ];

    static ref FORMATTING_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)formatting\s*(?:issue|error|violation)").unwrap(),
        Regex::new(r"(?i)indentation").unwrap(),
        Regex::new(r"(?i)trailing\s*whitespace").unwrap(),
        Regex::new(r"(?i)line\s*(?:too\s*long|length)").unwrap(),
        Regex::new(r"(?i)black\s*(?:format|style)").unwrap(),
        Regex::new(r"(?i)prettier").unwrap(),
    ];

    static ref LINTING_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)lint(?:ing)?\s*(?:error|warning|issue)").unwrap(),
        Regex::new(r"(?i)(?:flake8|pylint|eslint|mypy)\s*(?:error|warning)").unwrap(),
        Regex::new(r"(?i)\b(?:e\d{3}|w\d{3}|c\d{3})\b").unwrap(),
    ];

    static ref UNUSED_IMPORT_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)unused\s*import").unwrap(),
        Regex::new(r"(?i)import\s*\w+\s*(?:is\s*)?never\s*used").unwrap(),
        Regex::new(r"(?i)\bf401\b").unwrap(),
    ];

    static ref UNUSED_VARIABLE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)unused\s*(?:variable|argument|parameter)").unwrap(),
        Regex::new(r"(?i)(?:variable|argument)\s*\w+\s*(?:is\s*)?never\s*used").unwrap(),
        Regex::new(r"(?i)\bf841\b").unwrap(),
    ];

    // Medium confidence patterns
    static ref ERROR_HANDLING_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:add|missing)\s*(?:error|exception)\s*handling").unwrap(),
        Regex::new(r"(?i)(?:unhandled|uncaught)\s*(?:error|exception)").unwrap(),
        Regex::new(r"(?i)bare\s*except").unwrap(),
        Regex::new(r"(?i)broad\s*exception").unwrap(),
    ];

    static ref NULL_CHECK_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:null|none|undefined)\s*(?:check|guard)").unwrap(),
        Regex::new(r"(?i)(?:potential|possible)\s*(?:null|none)\s*(?:reference|pointer)").unwrap(),
        Regex::new(r"(?i)optional\s*chaining").unwrap(),
    ];

    static ref DOCUMENTATION_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:missing|add)\s*(?:docstring|documentation|comment)").unwrap(),
        Regex::new(r"(?i)(?:update|fix)\s*(?:docstring|documentation)").unwrap(),
        Regex::new(r"(?i)(?:type\s*)?hint").unwrap(),
    ];

    static ref TEST_COVERAGE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:add|missing)\s*(?:test|unit\s*test)").unwrap(),
        Regex::new(r"(?i)test\s*coverage").unwrap(),
        Regex::new(r"(?i)(?:no|missing)\s*tests?\s*for").unwrap(),
    ];

    static ref PERFORMANCE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)performance\s*(?:issue|improvement|optimization)").unwrap(),
        Regex::new(r"(?i)(?:slow|inefficient)\s*(?:code|algorithm|query)").unwrap(),
        Regex::new(r"(?i)n\+1\s*(?:query|problem)").unwrap(),
        Regex::new(r"(?i)(?:cache|memoize|optimize)").unwrap(),
    ];

    // Low confidence patterns
    static ref ARCHITECTURAL_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:architecture|design)\s*(?:issue|change|decision)").unwrap(),
        Regex::new(r"(?i)refactor\s*(?:to|into|using)").unwrap(),
        Regex::new(r"(?i)(?:restructure|reorganize)\s*(?:code|module|package)").unwrap(),
        Regex::new(r"(?i)(?:extract|split)\s*(?:class|module|service)").unwrap(),
    ];

    static ref API_CHANGE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)api\s*(?:change|breaking|compatibility)").unwrap(),
        Regex::new(r"(?i)(?:public|external)\s*(?:interface|api)").unwrap(),
        Regex::new(r"(?i)(?:signature|parameter)\s*change").unwrap(),
        Regex::new(r"(?i)(?:rename|remove)\s*(?:method|function|endpoint)").unwrap(),
    ];

    static ref BREAKING_CHANGE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)breaking\s*change").unwrap(),
        Regex::new(r"(?i)backward[s]?\s*(?:in)?compatibility").unwrap(),
        Regex::new(r"(?i)(?:deprecate|remove)\s*(?:support|feature)").unwrap(),
    ];

    static ref DATA_MODEL_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:database|schema|model)\s*(?:change|migration)").unwrap(),
        Regex::new(r"(?i)(?:add|remove|modify)\s*(?:field|column|table)").unwrap(),
        Regex::new(r"(?i)data\s*(?:model|structure)\s*change").unwrap(),
    ];

    static ref BUSINESS_LOGIC_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)business\s*(?:logic|rule)").unwrap(),
        Regex::new(r"(?i)(?:algorithm|calculation)\s*(?:change|update)").unwrap(),
        Regex::new(r"(?i)(?:behavior|functionality)\s*change").unwrap(),
    ];

    static ref DEPENDENCY_UPDATE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:update|upgrade|bump)\s*(?:dependency|package|library)").unwrap(),
        Regex::new(r"(?i)(?:major|minor)\s*version\s*(?:update|upgrade)").unwrap(),
    ];

    static ref MULTIPLE_APPROACHES_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:could|might|may)\s*(?:also|alternatively)").unwrap(),
        Regex::new(r"(?i)(?:another|different)\s*(?:approach|way|option)").unwrap(),
        Regex::new(r"(?i)(?:consider|suggest)\s*(?:using|trying)").unwrap(),
        Regex::new(r"(?i)(?:trade-?off|decision|choice)").unwrap(),
    ];

    // False positive patterns
    static ref VERSION_ROLLBACK_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:revert|rollback|downgrade)\s*(?:to|back\s*to)\s*v?\d+").unwrap(),
        Regex::new(r"(?i)(?:use|switch\s*to)\s*v?\d+\s*instead").unwrap(),
        Regex::new(r"(?i)v\d+\s*(?:doesn't|does\s*not)\s*(?:exist|work)").unwrap(),
        Regex::new(r"(?i)(?:action|checkout|artifact).*(?:v\d+).*(?:not\s*(?:found|available|exist))").unwrap(),
    ];

    static ref EXISTENCE_CLAIM_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:does\s*not|doesn't)\s*(?:exist|work|support)").unwrap(),
        Regex::new(r"(?i)(?:not\s*(?:a\s*)?valid|invalid)\s*(?:action|version|syntax)").unwrap(),
        Regex::new(r"(?i)(?:no\s*such|unknown)\s*(?:action|command|option)").unwrap(),
    ];

    static ref FIX_WORKING_CODE_PATTERNS: Vec<Regex> = vec![
        Regex::new(r"(?i)(?:this\s*)?(?:will|would|might|could)\s*(?:fail|break|crash)").unwrap(),
        Regex::new(r"(?i)(?:won't|will\s*not)\s*(?:work|compile|run)").unwrap(),
    ];

    // Analysis patterns
    static ref ACTION_REQUEST_PATTERN: Regex = Regex::new(r"(?i)(?:please|should|must|need\s*to)\s+\w+").unwrap();
    static ref FILE_REFERENCE_PATTERN: Regex = Regex::new(r"(?i)(?:line\s*\d+|file\s*\w+|\w+\.\w+:\d+)").unwrap();
    static ref UNCERTAIN_LANGUAGE_PATTERN: Regex = Regex::new(r"(?i)(?:maybe|might|could\s*consider|not\s*sure)").unwrap();
}

/// Pipeline success indicators.
const PIPELINE_SUCCESS_INDICATORS: &[&str] = &[
    "checkout succeeded",
    "artifact uploaded",
    "build passed",
    "tests passed",
    "workflow completed",
    "step succeeded",
    "job completed successfully",
];

/// Confidence thresholds.
const HIGH_CONFIDENCE_THRESHOLD: f64 = 0.85;
const MEDIUM_CONFIDENCE_THRESHOLD: f64 = 0.6;
const AUTO_FIX_THRESHOLD: f64 = 0.7;

/// Agent judgement system.
#[derive(Debug, Clone)]
pub struct AgentJudgement {
    #[allow(dead_code)]
    project_owners: Vec<String>,
}

impl Default for AgentJudgement {
    fn default() -> Self {
        Self::new(Vec::new())
    }
}

impl AgentJudgement {
    /// Create a new agent judgement system.
    pub fn new(project_owners: Vec<String>) -> Self {
        Self { project_owners }
    }

    /// Detect if an AI reviewer suggestion is a false positive.
    fn detect_false_positive(
        &self,
        review_comment: &str,
        context: &AssessmentContext,
    ) -> (bool, Option<String>) {
        let comment_lower = review_comment.to_lowercase();

        // Check for false positive patterns
        let mut matched_pattern = None;
        let mut pattern_type = None;

        for pattern in VERSION_ROLLBACK_PATTERNS.iter() {
            if pattern.is_match(&comment_lower) {
                matched_pattern = Some("version_rollback");
                pattern_type = Some("version_rollback");
                break;
            }
        }

        if matched_pattern.is_none() {
            for pattern in EXISTENCE_CLAIM_PATTERNS.iter() {
                if pattern.is_match(&comment_lower) {
                    matched_pattern = Some("existence_claims");
                    pattern_type = Some("existence_claims");
                    break;
                }
            }
        }

        if matched_pattern.is_none() {
            for pattern in FIX_WORKING_CODE_PATTERNS.iter() {
                if pattern.is_match(&comment_lower) {
                    matched_pattern = Some("fix_working_code");
                    pattern_type = Some("fix_working_code");
                    break;
                }
            }
        }

        if matched_pattern.is_none() {
            return (false, None);
        }

        // Check against reality
        let pipeline_status = context
            .pipeline_status
            .as_ref()
            .map(|s| s.to_lowercase())
            .unwrap_or_default();

        let pipeline_succeeded = PIPELINE_SUCCESS_INDICATORS
            .iter()
            .any(|ind| pipeline_status.contains(ind))
            || context.job_results.values().any(|result| {
                let r = result.to_lowercase();
                r == "success" || r == "passed" || r == "completed"
            });

        // Check for version rollback suggestions
        if pattern_type == Some("version_rollback") {
            // Check if we recently updated versions
            let version_update_keywords = ["update", "upgrade", "bump", "v6", "v5"];
            if !context.recent_commits.is_empty()
                && context.recent_commits.iter().any(|commit| {
                    version_update_keywords
                        .iter()
                        .any(|kw| commit.to_lowercase().contains(kw))
                })
            {
                return (
                    true,
                    Some(
                        "Version rollback suggestion contradicts recent intentional version update in commit history".to_string(),
                    ),
                );
            }
        }

        // Check for existence claims when pipeline succeeded
        if pattern_type == Some("existence_claims") && pipeline_succeeded {
            return (
                true,
                Some(
                    "Claim about non-existent feature is a false positive: pipeline completed successfully".to_string(),
                ),
            );
        }

        // Check for "will fail" predictions that didn't fail
        if pattern_type == Some("fix_working_code") && pipeline_succeeded {
            return (
                true,
                Some(
                    "Prediction of failure is a false positive: code ran successfully in pipeline"
                        .to_string(),
                ),
            );
        }

        (false, None)
    }

    /// Assess whether to auto-fix or ask for guidance.
    pub fn assess_fix(&self, review_comment: &str, context: &AssessmentContext) -> JudgementResult {
        // First: check for false positives
        let (is_false_positive, dismiss_reason) =
            self.detect_false_positive(review_comment, context);
        if is_false_positive {
            return JudgementResult {
                should_auto_fix: false,
                confidence: 0.0,
                category: FixCategory::FalsePositive,
                reasoning: dismiss_reason
                    .clone()
                    .unwrap_or_else(|| "AI reviewer suggestion contradicts observable reality".to_string()),
                ask_owner_question: None,
                is_false_positive: true,
                dismiss_reason,
            };
        }

        // Check high-confidence patterns first
        if let Some((category, confidence, reasoning)) =
            self.check_high_confidence_patterns(review_comment)
        {
            return JudgementResult {
                should_auto_fix: true,
                confidence,
                category,
                reasoning,
                ask_owner_question: None,
                is_false_positive: false,
                dismiss_reason: None,
            };
        }

        // Check low-confidence patterns (take precedence over medium)
        if let Some((category, reasoning)) = self.check_low_confidence_patterns(review_comment) {
            let question = self.generate_owner_question(category, review_comment);
            return JudgementResult {
                should_auto_fix: false,
                confidence: 0.3,
                category,
                reasoning,
                ask_owner_question: Some(question),
                is_false_positive: false,
                dismiss_reason: None,
            };
        }

        // Check medium-confidence patterns
        if let Some((category, base_confidence)) =
            self.check_medium_confidence_patterns(review_comment)
        {
            let confidence = self.calculate_medium_confidence(base_confidence, context);
            let should_fix = confidence >= AUTO_FIX_THRESHOLD;

            if should_fix {
                return JudgementResult {
                    should_auto_fix: true,
                    confidence,
                    category,
                    reasoning: format!(
                        "Medium-confidence fix with sufficient context: {}",
                        category
                    ),
                    ask_owner_question: None,
                    is_false_positive: false,
                    dismiss_reason: None,
                };
            } else {
                let question = self.generate_owner_question(category, review_comment);
                return JudgementResult {
                    should_auto_fix: false,
                    confidence,
                    category,
                    reasoning: format!(
                        "Medium-confidence fix but insufficient context: {}",
                        category
                    ),
                    ask_owner_question: Some(question),
                    is_false_positive: false,
                    dismiss_reason: None,
                };
            }
        }

        // Unknown category
        let (confidence, reasoning) = self.analyze_unknown_feedback(review_comment, context);
        if confidence >= AUTO_FIX_THRESHOLD {
            JudgementResult {
                should_auto_fix: true,
                confidence,
                category: FixCategory::Unknown,
                reasoning,
                ask_owner_question: None,
                is_false_positive: false,
                dismiss_reason: None,
            }
        } else {
            let question = self.generate_owner_question(FixCategory::Unknown, review_comment);
            JudgementResult {
                should_auto_fix: false,
                confidence,
                category: FixCategory::Unknown,
                reasoning,
                ask_owner_question: Some(question),
                is_false_positive: false,
                dismiss_reason: None,
            }
        }
    }

    /// Check high-confidence patterns.
    fn check_high_confidence_patterns(
        &self,
        review_comment: &str,
    ) -> Option<(FixCategory, f64, String)> {
        // Security vulnerability - highest priority
        for pattern in SECURITY_PATTERNS.iter() {
            if pattern.is_match(review_comment) {
                return Some((
                    FixCategory::SecurityVulnerability,
                    0.95,
                    format!(
                        "Security vulnerability detected: {}. Auto-fixing is critical.",
                        pattern.as_str()
                    ),
                ));
            }
        }

        // Other high-confidence categories
        let high_confidence_checks: &[(&[Regex], FixCategory)] = &[
            (&SYNTAX_PATTERNS, FixCategory::SyntaxError),
            (&TYPE_PATTERNS, FixCategory::TypeError),
            (&IMPORT_PATTERNS, FixCategory::ImportError),
            (&FORMATTING_PATTERNS, FixCategory::Formatting),
            (&LINTING_PATTERNS, FixCategory::Linting),
            (&UNUSED_IMPORT_PATTERNS, FixCategory::UnusedImport),
            (&UNUSED_VARIABLE_PATTERNS, FixCategory::UnusedVariable),
        ];

        for (patterns, category) in high_confidence_checks {
            for pattern in patterns.iter() {
                if pattern.is_match(review_comment) {
                    return Some((
                        *category,
                        HIGH_CONFIDENCE_THRESHOLD,
                        format!("High-confidence fix category: {}", category),
                    ));
                }
            }
        }

        None
    }

    /// Check medium-confidence patterns.
    fn check_medium_confidence_patterns(
        &self,
        review_comment: &str,
    ) -> Option<(FixCategory, f64)> {
        let medium_checks: &[(&[Regex], FixCategory)] = &[
            (&ERROR_HANDLING_PATTERNS, FixCategory::ErrorHandling),
            (&NULL_CHECK_PATTERNS, FixCategory::NullCheck),
            (&DOCUMENTATION_PATTERNS, FixCategory::Documentation),
            (&TEST_COVERAGE_PATTERNS, FixCategory::TestCoverage),
            (&PERFORMANCE_PATTERNS, FixCategory::Performance),
        ];

        for (patterns, category) in medium_checks {
            for pattern in patterns.iter() {
                if pattern.is_match(review_comment) {
                    return Some((*category, MEDIUM_CONFIDENCE_THRESHOLD));
                }
            }
        }

        None
    }

    /// Check low-confidence patterns.
    fn check_low_confidence_patterns(&self, review_comment: &str) -> Option<(FixCategory, String)> {
        let low_checks: &[(&[Regex], FixCategory)] = &[
            (&ARCHITECTURAL_PATTERNS, FixCategory::Architectural),
            (&API_CHANGE_PATTERNS, FixCategory::ApiChange),
            (&BREAKING_CHANGE_PATTERNS, FixCategory::BreakingChange),
            (&DATA_MODEL_PATTERNS, FixCategory::DataModel),
            (&BUSINESS_LOGIC_PATTERNS, FixCategory::BusinessLogic),
            (&DEPENDENCY_UPDATE_PATTERNS, FixCategory::DependencyUpdate),
            (&MULTIPLE_APPROACHES_PATTERNS, FixCategory::MultipleApproaches),
        ];

        for (patterns, category) in low_checks {
            for pattern in patterns.iter() {
                if pattern.is_match(review_comment) {
                    return Some((
                        *category,
                        format!(
                            "Low-confidence category requiring human decision: {}",
                            category
                        ),
                    ));
                }
            }
        }

        None
    }

    /// Calculate confidence for medium-confidence categories.
    fn calculate_medium_confidence(&self, base_confidence: f64, context: &AssessmentContext) -> f64 {
        let mut confidence = base_confidence;

        // Boost confidence if we have good context
        if context.file_path.is_some() {
            confidence += 0.05;
        }
        if context.diff.is_some() {
            confidence += 0.05;
        }
        if context.existing_tests {
            confidence += 0.1;
        }

        // Reduce confidence for risky scenarios
        if context.is_security_related {
            confidence -= 0.1;
        }
        if context.touches_api {
            confidence -= 0.15;
        }
        if context.touches_database {
            confidence -= 0.15;
        }

        // Cap at reasonable bounds
        confidence.clamp(0.3, 0.85)
    }

    /// Analyze unknown feedback to estimate confidence.
    fn analyze_unknown_feedback(
        &self,
        review_comment: &str,
        context: &AssessmentContext,
    ) -> (f64, String) {
        let mut confidence: f64 = 0.5;
        let mut reasons = Vec::new();

        // Check for specific, actionable language
        if ACTION_REQUEST_PATTERN.is_match(review_comment) {
            confidence += 0.1;
            reasons.push("Contains specific action request");
        }

        // Check for code suggestions
        if review_comment.contains("```") {
            confidence += 0.15;
            reasons.push("Contains code suggestion");
        }

        // Check for file/line references
        if FILE_REFERENCE_PATTERN.is_match(review_comment) {
            confidence += 0.1;
            reasons.push("References specific location");
        }

        // Reduce confidence for vague feedback
        if UNCERTAIN_LANGUAGE_PATTERN.is_match(review_comment) {
            confidence -= 0.15;
            reasons.push("Contains uncertain language");
        }

        // Reduce confidence for questions
        if review_comment.matches('?').count() > 1 {
            confidence -= 0.1;
            reasons.push("Contains multiple questions");
        }

        // Adjust based on context
        if context.is_draft_pr {
            confidence -= 0.1;
            reasons.push("PR is still in draft");
        }

        confidence = confidence.clamp(0.2, 0.8);
        let reasoning = if reasons.is_empty() {
            "General feedback analysis".to_string()
        } else {
            reasons.join("; ")
        };

        (confidence, reasoning)
    }

    /// Generate a question to ask the project owner.
    fn generate_owner_question(&self, category: FixCategory, review_comment: &str) -> String {
        let review_summary = if review_comment.len() > 200 {
            format!("{}...", &review_comment[..200])
        } else {
            review_comment.to_string()
        };

        match category {
            FixCategory::Architectural => format!(
                "This review suggests an architectural change. How would you like me to proceed?\n\n\
                > {}\n\n\
                Options:\n\
                1. Implement the suggested change\n\
                2. Keep current approach and explain reasoning\n\
                3. Discuss alternative approaches",
                review_summary
            ),
            FixCategory::ApiChange => format!(
                "This review suggests a change that may affect the API. \
                Should I proceed with the modification?\n\n\
                > {}\n\n\
                This could affect other parts of the codebase or external consumers.",
                review_summary
            ),
            FixCategory::BreakingChange => format!(
                "This review suggests a potentially breaking change. \
                Do you want me to implement this?\n\n\
                > {}\n\n\
                Please confirm if backward compatibility is not a concern.",
                review_summary
            ),
            FixCategory::DataModel => format!(
                "This review suggests changes to the data model. How should I handle this?\n\n\
                > {}\n\n\
                This may require database migrations or affect existing data.",
                review_summary
            ),
            FixCategory::BusinessLogic => format!(
                "This review suggests changes to business logic. \
                Can you clarify the expected behavior?\n\n> {}",
                review_summary
            ),
            FixCategory::DependencyUpdate => format!(
                "This review suggests updating dependencies. Should I proceed with the update?\n\n\
                > {}\n\n\
                This may introduce breaking changes or require additional testing.",
                review_summary
            ),
            FixCategory::MultipleApproaches => format!(
                "This review presents multiple possible approaches. \
                Which approach would you prefer?\n\n> {}",
                review_summary
            ),
            _ => format!(
                "I need guidance on this review feedback:\n\n> {}",
                review_summary
            ),
        }
    }

    /// Check if we should ask the owner for guidance.
    pub fn should_ask_owner(&self, result: &JudgementResult) -> bool {
        // Never ask owner about false positives
        if result.is_false_positive {
            return false;
        }
        !result.should_auto_fix && result.ask_owner_question.is_some()
    }

    /// Check if the suggestion should be dismissed (false positive).
    pub fn should_dismiss(&self, result: &JudgementResult) -> bool {
        result.is_false_positive
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_high_confidence_security() {
        let judgement = AgentJudgement::default();
        let result = judgement.assess_fix("SQL injection vulnerability detected", &AssessmentContext::default());

        assert!(result.should_auto_fix);
        assert_eq!(result.category, FixCategory::SecurityVulnerability);
        assert!(result.confidence >= 0.9);
    }

    #[test]
    fn test_high_confidence_linting() {
        let judgement = AgentJudgement::default();
        // Use a lint error code that only matches linting, not formatting
        let result = judgement.assess_fix("flake8 error W503: line break before binary operator", &AssessmentContext::default());

        assert!(result.should_auto_fix);
        assert_eq!(result.category, FixCategory::Linting);
    }

    #[test]
    fn test_low_confidence_architectural() {
        let judgement = AgentJudgement::default();
        // "architecture decision" matches the architectural pattern
        let result = judgement.assess_fix("This is an architecture decision that needs review", &AssessmentContext::default());

        assert!(!result.should_auto_fix);
        assert_eq!(result.category, FixCategory::Architectural);
        assert!(result.ask_owner_question.is_some());
    }

    #[test]
    fn test_false_positive_detection() {
        let judgement = AgentJudgement::default();
        let mut context = AssessmentContext::default();
        context.job_results.insert("build".to_string(), "success".to_string());

        let result = judgement.assess_fix("This code won't work and will fail", &context);

        assert!(result.is_false_positive);
        assert!(!result.should_auto_fix);
        assert_eq!(result.category, FixCategory::FalsePositive);
    }

    #[test]
    fn test_unused_import() {
        let judgement = AgentJudgement::default();
        let result = judgement.assess_fix("F401 unused import 'os'", &AssessmentContext::default());

        assert!(result.should_auto_fix);
        assert_eq!(result.category, FixCategory::UnusedImport);
    }
}
