//! Agent judgement system for assessing when to auto-fix vs ask for guidance.
//!
//! This module provides heuristic decision-making for AI agents to determine
//! whether they should automatically implement fixes or ask project owners
//! for guidance on uncertain changes.
//!
//! Includes false positive detection to avoid acting on AI reviewer suggestions
//! that contradict observable reality (e.g. "this will fail" when the pipeline
//! passed).

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::LazyLock;

fn compile_one(pattern: &str) -> Regex {
    Regex::new(pattern).expect("judgement regex is valid")
}

/// Declare lazily compiled pattern lists.
macro_rules! patterns {
    ($($(#[$meta:meta])* $name:ident = [$($p:literal),+ $(,)?];)+) => {
        $(
            $(#[$meta])*
            static $name: LazyLock<Vec<Regex>> =
                LazyLock::new(|| [$($p),+].iter().map(|p| compile_one(p)).collect());
        )+
    };
}

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
    pub is_security_related: bool,
    pub is_draft_pr: bool,
    pub touches_api: bool,
    pub touches_database: bool,
    pub existing_tests: bool,
    pub pipeline_status: Option<String>,
    pub job_results: HashMap<String, String>,
    pub recent_commits: Vec<String>,
}

patterns! {
    // High confidence patterns
    SECURITY_PATTERNS = [
        r"(?i)sql\s*injection",
        r"(?i)xss\s*(vulnerability)?",
        r"(?i)command\s*injection",
        r"(?i)path\s*traversal",
        r"(?i)insecure\s*(?:random|hash|password)",
        r"(?i)hardcoded\s*(?:password|secret|key|credential)",
        r"(?i)sensitive\s*data\s*(?:exposed|leak)",
        r"(?i)authentication\s*bypass",
        r"(?i)authorization\s*(?:issue|bypass|flaw)",
    ];

    SYNTAX_PATTERNS = [
        r"(?i)syntax\s*error",
        r"(?i)invalid\s*syntax",
        r"(?i)unexpected\s*token",
        r"(?i)missing\s*(?:bracket|parenthesis|colon|semicolon)",
    ];

    TYPE_PATTERNS = [
        r"(?i)type\s*error",
        r"(?i)type\s*mismatch",
        r"(?i)incompatible\s*type",
        r"(?i)wrong\s*type",
        r"(?i)expected\s*\w+\s*(?:but\s*)?got\s*\w+",
    ];

    IMPORT_PATTERNS = [
        r"(?i)import\s*error",
        r"(?i)module\s*not\s*found",
        r"(?i)cannot\s*(?:find|import)\s*module",
        r"(?i)unresolved\s*(?:import|reference)",
    ];

    FORMATTING_PATTERNS = [
        r"(?i)formatting\s*(?:issue|error|violation)",
        r"(?i)indentation",
        r"(?i)trailing\s*whitespace",
        r"(?i)line\s*(?:too\s*long|length)",
        r"(?i)black\s*(?:format|style)",
        r"(?i)prettier",
    ];

    LINTING_PATTERNS = [
        r"(?i)lint(?:ing)?\s*(?:error|warning|issue)",
        r"(?i)(?:flake8|pylint|ruff|eslint|mypy)\s*(?:error|warning)",
        r"(?i)\b(?:e\d{3}|w\d{3}|c\d{3})\b",
    ];

    UNUSED_IMPORT_PATTERNS = [
        r"(?i)unused\s*import",
        r"(?i)import\s*\w+\s*(?:is\s*)?never\s*used",
        r"(?i)\bf401\b",
    ];

    UNUSED_VARIABLE_PATTERNS = [
        r"(?i)unused\s*(?:variable|argument|parameter)",
        r"(?i)(?:variable|argument)\s*\w+\s*(?:is\s*)?never\s*used",
        r"(?i)\bf841\b",
    ];

    // Medium confidence patterns
    ERROR_HANDLING_PATTERNS = [
        r"(?i)(?:add|missing)\s*(?:error|exception)\s*handling",
        r"(?i)(?:unhandled|uncaught)\s*(?:error|exception)",
        r"(?i)bare\s*except",
        r"(?i)broad\s*exception",
    ];

    NULL_CHECK_PATTERNS = [
        r"(?i)(?:null|none|undefined)\s*(?:check|guard)",
        r"(?i)(?:potential|possible)\s*(?:null|none)\s*(?:reference|pointer)",
        r"(?i)optional\s*chaining",
    ];

    DOCUMENTATION_PATTERNS = [
        r"(?i)(?:missing|add)\s*(?:docstring|documentation|comment)",
        r"(?i)(?:update|fix)\s*(?:docstring|documentation)",
        r"(?i)(?:type\s*)?hint",
    ];

    TEST_COVERAGE_PATTERNS = [
        r"(?i)(?:add|missing)\s*(?:test|unit\s*test)",
        r"(?i)test\s*coverage",
        r"(?i)(?:no|missing)\s*tests?\s*for",
    ];

    PERFORMANCE_PATTERNS = [
        r"(?i)performance\s*(?:issue|improvement|optimization)",
        r"(?i)(?:slow|inefficient)\s*(?:code|algorithm|query)",
        r"(?i)n\+1\s*(?:query|problem)",
        r"(?i)(?:cache|memoize|optimize)",
    ];

    // Low confidence patterns
    ARCHITECTURAL_PATTERNS = [
        r"(?i)(?:architecture|design)\s*(?:issue|change|decision)",
        r"(?i)refactor\s*(?:to|into|using)",
        r"(?i)(?:restructure|reorganize)\s*(?:code|module|package)",
        r"(?i)(?:extract|split)\s*(?:class|module|service)",
    ];

    API_CHANGE_PATTERNS = [
        r"(?i)api\s*(?:change|breaking|compatibility)",
        r"(?i)(?:public|external)\s*(?:interface|api)",
        r"(?i)(?:signature|parameter)\s*change",
        r"(?i)(?:rename|remove)\s*(?:method|function|endpoint)",
    ];

    BREAKING_CHANGE_PATTERNS = [
        r"(?i)breaking\s*change",
        r"(?i)backward[s]?\s*(?:in)?compatibility",
        r"(?i)(?:deprecate|remove)\s*(?:support|feature)",
    ];

    DATA_MODEL_PATTERNS = [
        r"(?i)(?:database|schema|model)\s*(?:change|migration)",
        r"(?i)(?:add|remove|modify)\s*(?:field|column|table)",
        r"(?i)data\s*(?:model|structure)\s*change",
    ];

    BUSINESS_LOGIC_PATTERNS = [
        r"(?i)business\s*(?:logic|rule)",
        r"(?i)(?:algorithm|calculation)\s*(?:change|update)",
        r"(?i)(?:behavior|functionality)\s*change",
    ];

    DEPENDENCY_UPDATE_PATTERNS = [
        r"(?i)(?:update|upgrade|bump)\s*(?:dependency|package|library)",
        r"(?i)(?:major|minor)\s*version\s*(?:update|upgrade)",
    ];

    MULTIPLE_APPROACHES_PATTERNS = [
        r"(?i)(?:could|might|may)\s*(?:also|alternatively)",
        r"(?i)(?:another|different)\s*(?:approach|way|option)",
        r"(?i)(?:consider|suggest)\s*(?:using|trying)",
        r"(?i)(?:trade-?off|decision|choice)",
    ];

    // False positive patterns
    VERSION_ROLLBACK_PATTERNS = [
        r"(?i)(?:revert|rollback|downgrade)\s*(?:to|back\s*to)\s*v?\d+",
        r"(?i)(?:use|switch\s*to)\s*v?\d+\s*instead",
        r"(?i)v\d+\s*(?:doesn't|does\s*not)\s*(?:exist|work)",
        r"(?i)(?:action|checkout|artifact).*(?:v\d+).*(?:not\s*(?:found|available|exist))",
    ];

    EXISTENCE_CLAIM_PATTERNS = [
        r"(?i)(?:does\s*not|doesn't)\s*(?:exist|work|support)",
        r"(?i)(?:not\s*(?:a\s*)?valid|invalid)\s*(?:action|version|syntax)",
        r"(?i)(?:no\s*such|unknown)\s*(?:action|command|option)",
    ];

    FIX_WORKING_CODE_PATTERNS = [
        r"(?i)(?:this\s*)?(?:will|would|might|could)\s*(?:fail|break|crash)",
        r"(?i)(?:won't|will\s*not)\s*(?:work|compile|run)",
    ];
}

// Analysis patterns
static ACTION_REQUEST_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| compile_one(r"(?i)(?:please|should|must|need\s*to)\s+\w+"));
static FILE_REFERENCE_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| compile_one(r"(?i)(?:line\s*\d+|file\s*\w+|\w+\.\w+:\d+)"));
static UNCERTAIN_LANGUAGE_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| compile_one(r"(?i)(?:maybe|might|could\s*consider|not\s*sure)"));

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

/// Kinds of claims AI reviewers make that can be checked against reality.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum FalsePositiveKind {
    VersionRollback,
    ExistenceClaim,
    PredictedFailure,
}

fn any_match(patterns: &[Regex], text: &str) -> bool {
    patterns.iter().any(|p| p.is_match(text))
}

/// Agent judgement system.
#[derive(Debug, Clone, Default)]
pub struct AgentJudgement;

impl AgentJudgement {
    /// Detect if an AI reviewer suggestion is a false positive.
    /// Returns the dismiss reason when it is.
    fn detect_false_positive(
        &self,
        review_comment: &str,
        context: &AssessmentContext,
    ) -> Option<String> {
        let comment = review_comment.to_lowercase();
        let kind = if any_match(&VERSION_ROLLBACK_PATTERNS, &comment) {
            FalsePositiveKind::VersionRollback
        } else if any_match(&EXISTENCE_CLAIM_PATTERNS, &comment) {
            FalsePositiveKind::ExistenceClaim
        } else if any_match(&FIX_WORKING_CODE_PATTERNS, &comment) {
            FalsePositiveKind::PredictedFailure
        } else {
            return None;
        };

        let pipeline_status = context
            .pipeline_status
            .as_deref()
            .unwrap_or_default()
            .to_lowercase();
        let pipeline_succeeded = PIPELINE_SUCCESS_INDICATORS
            .iter()
            .any(|ind| pipeline_status.contains(ind))
            || context.job_results.values().any(|result| {
                matches!(
                    result.to_lowercase().as_str(),
                    "success" | "passed" | "completed"
                )
            });

        match kind {
            FalsePositiveKind::VersionRollback => {
                const KEYWORDS: [&str; 5] = ["update", "upgrade", "bump", "v6", "v5"];
                context
                    .recent_commits
                    .iter()
                    .any(|c| {
                        let c = c.to_lowercase();
                        KEYWORDS.iter().any(|kw| c.contains(kw))
                    })
                    .then(|| {
                        "Version rollback suggestion contradicts recent intentional version \
                         update in commit history"
                            .to_string()
                    })
            },
            FalsePositiveKind::ExistenceClaim => pipeline_succeeded.then(|| {
                "Claim about non-existent feature is a false positive: pipeline completed \
                 successfully"
                    .to_string()
            }),
            FalsePositiveKind::PredictedFailure => pipeline_succeeded.then(|| {
                "Prediction of failure is a false positive: code ran successfully in pipeline"
                    .to_string()
            }),
        }
    }

    /// Assess whether to auto-fix or ask for guidance.
    pub fn assess_fix(&self, review_comment: &str, context: &AssessmentContext) -> JudgementResult {
        // First: check for false positives
        if let Some(reason) = self.detect_false_positive(review_comment, context) {
            return JudgementResult {
                should_auto_fix: false,
                confidence: 0.0,
                category: FixCategory::FalsePositive,
                reasoning: reason.clone(),
                ask_owner_question: None,
                is_false_positive: true,
                dismiss_reason: Some(reason),
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
    fn check_medium_confidence_patterns(&self, review_comment: &str) -> Option<(FixCategory, f64)> {
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
            (
                &MULTIPLE_APPROACHES_PATTERNS,
                FixCategory::MultipleApproaches,
            ),
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
    fn calculate_medium_confidence(
        &self,
        base_confidence: f64,
        context: &AssessmentContext,
    ) -> f64 {
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
        // Truncate on a char boundary (byte slicing could panic on UTF-8) and
        // quote every line so multi-line comments stay inside the blockquote.
        let review_summary = crate::client::truncate(review_comment.trim(), 200)
            .lines()
            .map(|l| format!("> {}", l))
            .collect::<Vec<_>>()
            .join("\n");

        match category {
            FixCategory::Architectural => format!(
                "This review suggests an architectural change. How would you like me to proceed?\n\n\
                {}\n\n\
                Options:\n\
                1. Implement the suggested change\n\
                2. Keep current approach and explain reasoning\n\
                3. Discuss alternative approaches",
                review_summary
            ),
            FixCategory::ApiChange => format!(
                "This review suggests a change that may affect the API. \
                Should I proceed with the modification?\n\n\
                {}\n\n\
                This could affect other parts of the codebase or external consumers.",
                review_summary
            ),
            FixCategory::BreakingChange => format!(
                "This review suggests a potentially breaking change. \
                Do you want me to implement this?\n\n\
                {}\n\n\
                Please confirm if backward compatibility is not a concern.",
                review_summary
            ),
            FixCategory::DataModel => format!(
                "This review suggests changes to the data model. How should I handle this?\n\n\
                {}\n\n\
                This may require database migrations or affect existing data.",
                review_summary
            ),
            FixCategory::BusinessLogic => format!(
                "This review suggests changes to business logic. \
                Can you clarify the expected behavior?\n\n{}",
                review_summary
            ),
            FixCategory::DependencyUpdate => format!(
                "This review suggests updating dependencies. Should I proceed with the update?\n\n\
                {}\n\n\
                This may introduce breaking changes or require additional testing.",
                review_summary
            ),
            FixCategory::MultipleApproaches => format!(
                "This review presents multiple possible approaches. \
                Which approach would you prefer?\n\n{}",
                review_summary
            ),
            _ => format!(
                "I need guidance on this review feedback:\n\n{}",
                review_summary
            ),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_high_confidence_security() {
        let judgement = AgentJudgement;
        let result = judgement.assess_fix(
            "SQL injection vulnerability detected",
            &AssessmentContext::default(),
        );

        assert!(result.should_auto_fix);
        assert_eq!(result.category, FixCategory::SecurityVulnerability);
        assert!(result.confidence >= 0.9);
    }

    #[test]
    fn test_high_confidence_linting() {
        let judgement = AgentJudgement;
        // Use a lint error code that only matches linting, not formatting
        let result = judgement.assess_fix(
            "flake8 error W503: line break before binary operator",
            &AssessmentContext::default(),
        );

        assert!(result.should_auto_fix);
        assert_eq!(result.category, FixCategory::Linting);
    }

    #[test]
    fn test_low_confidence_architectural() {
        let judgement = AgentJudgement;
        // "architecture decision" matches the architectural pattern
        let result = judgement.assess_fix(
            "This is an architecture decision that needs review",
            &AssessmentContext::default(),
        );

        assert!(!result.should_auto_fix);
        assert_eq!(result.category, FixCategory::Architectural);
        assert!(result.ask_owner_question.is_some());
    }

    #[test]
    fn test_false_positive_detection() {
        let judgement = AgentJudgement;
        let mut context = AssessmentContext::default();
        context
            .job_results
            .insert("build".to_string(), "success".to_string());

        let result = judgement.assess_fix("This code won't work and will fail", &context);

        assert!(result.is_false_positive);
        assert!(!result.should_auto_fix);
        assert_eq!(result.category, FixCategory::FalsePositive);
    }

    #[test]
    fn test_unused_import() {
        let judgement = AgentJudgement;
        let result = judgement.assess_fix("F401 unused import 'os'", &AssessmentContext::default());

        assert!(result.should_auto_fix);
        assert_eq!(result.category, FixCategory::UnusedImport);
    }

    #[test]
    fn long_non_ascii_comment_does_not_panic() {
        // 199 ASCII bytes followed by a multi-byte char straddling byte 200.
        let comment = format!("{}\u{00e9}{}", "a".repeat(199), " design change".repeat(20));
        let result = AgentJudgement.assess_fix(&comment, &AssessmentContext::default());
        let question = result.ask_owner_question.unwrap_or_default();
        assert!(question.contains("..."));
    }

    #[test]
    fn owner_question_quotes_every_line() {
        let result = AgentJudgement.assess_fix(
            "This is an architecture decision.\nSecond line here.",
            &AssessmentContext::default(),
        );
        let q = result.ask_owner_question.unwrap();
        assert!(q.contains("> This is an architecture decision.\n> Second line here."));
    }

    #[test]
    fn version_rollback_false_positive_needs_recent_bump() {
        let comment = "Please revert to v4, v5 does not exist";
        let plain = AgentJudgement.assess_fix(comment, &AssessmentContext::default());
        assert!(!plain.is_false_positive);

        let ctx = AssessmentContext {
            recent_commits: vec!["chore: bump actions/checkout to v5".into()],
            ..Default::default()
        };
        let result = AgentJudgement.assess_fix(comment, &ctx);
        assert!(result.is_false_positive);
        assert!(result.dismiss_reason.unwrap().contains("version update"));
    }

    #[test]
    fn predicted_failure_without_pipeline_evidence_is_not_dismissed() {
        let result =
            AgentJudgement.assess_fix("This will fail at runtime", &AssessmentContext::default());
        assert!(!result.is_false_positive);

        let ctx = AssessmentContext {
            pipeline_status: Some("All tests passed".into()),
            ..Default::default()
        };
        assert!(
            AgentJudgement
                .assess_fix("This will fail at runtime", &ctx)
                .is_false_positive
        );
    }

    #[test]
    fn medium_confidence_depends_on_context() {
        let comment = "Missing error handling around the file read";
        let bare = AgentJudgement.assess_fix(comment, &AssessmentContext::default());
        assert_eq!(bare.category, FixCategory::ErrorHandling);
        assert!(!bare.should_auto_fix);

        let rich = AssessmentContext {
            file_path: Some("src/io.rs".into()),
            diff: Some("+ read()".into()),
            existing_tests: true,
            ..Default::default()
        };
        let result = AgentJudgement.assess_fix(comment, &rich);
        assert!(result.should_auto_fix);
        assert!(result.confidence >= AUTO_FIX_THRESHOLD);
    }
}
