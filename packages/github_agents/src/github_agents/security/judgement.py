"""Agent judgement system for assessing when to auto-fix vs ask for guidance.

This module provides intelligent decision-making for AI agents to determine
whether they should automatically implement fixes or ask project owners
for guidance on uncertain changes.

Includes false positive detection to avoid acting on AI reviewer suggestions
that contradict observable reality (e.g., claiming something is broken when
the CI pipeline clearly succeeded).
"""

from dataclasses import dataclass
from enum import Enum
import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class FixCategory(Enum):
    """Categories of fixes with different confidence levels."""

    # High confidence - always auto-fix
    SECURITY_VULNERABILITY = "security_vulnerability"
    SYNTAX_ERROR = "syntax_error"
    TYPE_ERROR = "type_error"
    IMPORT_ERROR = "import_error"
    FORMATTING = "formatting"
    LINTING = "linting"
    MISSING_RETURN = "missing_return"
    UNUSED_IMPORT = "unused_import"
    UNUSED_VARIABLE = "unused_variable"

    # Medium confidence - auto-fix with caution
    ERROR_HANDLING = "error_handling"
    NULL_CHECK = "null_check"
    EDGE_CASE = "edge_case"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    TEST_COVERAGE = "test_coverage"

    # Low confidence - ask owner
    ARCHITECTURAL = "architectural"
    API_CHANGE = "api_change"
    BREAKING_CHANGE = "breaking_change"
    DATA_MODEL = "data_model"
    BUSINESS_LOGIC = "business_logic"
    DEPENDENCY_UPDATE = "dependency_update"
    MULTIPLE_APPROACHES = "multiple_approaches"

    # Unknown - analyze further or ask
    UNKNOWN = "unknown"

    # False positive - dismiss silently (AI reviewer was wrong)
    FALSE_POSITIVE = "false_positive"


@dataclass
class JudgementResult:
    """Result of agent judgement assessment."""

    should_auto_fix: bool
    confidence: float  # 0.0 to 1.0
    category: FixCategory
    reasoning: str
    ask_owner_question: Optional[str] = None  # Question to ask if not auto-fixing
    is_false_positive: bool = False  # True if suggestion contradicts observable reality
    dismiss_reason: Optional[str] = None  # Why the suggestion was dismissed


class AgentJudgement:
    """Assess whether agent should act autonomously or ask for guidance.

    This class analyzes review feedback and determines whether the agent
    should automatically implement fixes or ask the project owner for
    guidance on uncertain changes.
    """

    # Patterns that indicate high-confidence auto-fix scenarios
    HIGH_CONFIDENCE_PATTERNS = {
        FixCategory.SECURITY_VULNERABILITY: [
            r"sql\s*injection",
            r"xss\s*(vulnerability)?",
            r"command\s*injection",
            r"path\s*traversal",
            r"insecure\s*(?:random|hash|password)",
            r"hardcoded\s*(?:password|secret|key|credential)",
            r"sensitive\s*data\s*(?:exposed|leak)",
            r"authentication\s*bypass",
            r"authorization\s*(?:issue|bypass|flaw)",
        ],
        FixCategory.SYNTAX_ERROR: [
            r"syntax\s*error",
            r"invalid\s*syntax",
            r"unexpected\s*token",
            r"missing\s*(?:bracket|parenthesis|colon|semicolon)",
        ],
        FixCategory.TYPE_ERROR: [
            r"type\s*error",
            r"type\s*mismatch",
            r"incompatible\s*type",
            r"wrong\s*type",
            r"expected\s*\w+\s*(?:but\s*)?got\s*\w+",
        ],
        FixCategory.IMPORT_ERROR: [
            r"import\s*error",
            r"module\s*not\s*found",
            r"cannot\s*(?:find|import)\s*module",
            r"unresolved\s*(?:import|reference)",
        ],
        FixCategory.FORMATTING: [
            r"formatting\s*(?:issue|error|violation)",
            r"indentation",
            r"trailing\s*whitespace",
            r"line\s*(?:too\s*long|length)",
            r"black\s*(?:format|style)",
            r"prettier",
        ],
        FixCategory.LINTING: [
            r"lint(?:ing)?\s*(?:error|warning|issue)",
            r"(?:flake8|pylint|eslint|mypy)\s*(?:error|warning)",
            r"(?:e\d{3}|w\d{3}|c\d{3})\b",  # Error codes like E501, W503
        ],
        FixCategory.UNUSED_IMPORT: [
            r"unused\s*import",
            r"import\s*\w+\s*(?:is\s*)?never\s*used",
            r"\bf401\b",  # flake8 unused import (word boundary to avoid false positives)
        ],
        FixCategory.UNUSED_VARIABLE: [
            r"unused\s*(?:variable|argument|parameter)",
            r"(?:variable|argument)\s*\w+\s*(?:is\s*)?never\s*used",
            r"\bf841\b",  # flake8 unused variable (word boundary to avoid false positives)
        ],
    }

    # Patterns that indicate medium-confidence scenarios
    MEDIUM_CONFIDENCE_PATTERNS = {
        FixCategory.ERROR_HANDLING: [
            r"(?:add|missing)\s*(?:error|exception)\s*handling",
            r"(?:unhandled|uncaught)\s*(?:error|exception)",
            r"bare\s*except",
            r"broad\s*exception",
        ],
        FixCategory.NULL_CHECK: [
            r"(?:null|none|undefined)\s*(?:check|guard)",
            r"(?:potential|possible)\s*(?:null|none)\s*(?:reference|pointer)",
            r"optional\s*chaining",
        ],
        FixCategory.DOCUMENTATION: [
            r"(?:missing|add)\s*(?:docstring|documentation|comment)",
            r"(?:update|fix)\s*(?:docstring|documentation)",
            r"(?:type\s*)?hint",
        ],
        FixCategory.TEST_COVERAGE: [
            r"(?:add|missing)\s*(?:test|unit\s*test)",
            r"test\s*coverage",
            r"(?:no|missing)\s*tests?\s*for",
        ],
        FixCategory.PERFORMANCE: [
            r"performance\s*(?:issue|improvement|optimization)",
            r"(?:slow|inefficient)\s*(?:code|algorithm|query)",
            r"n\+1\s*(?:query|problem)",
            r"(?:cache|memoize|optimize)",
        ],
    }

    # Patterns that indicate low-confidence scenarios (ask owner)
    LOW_CONFIDENCE_PATTERNS = {
        FixCategory.ARCHITECTURAL: [
            r"(?:architecture|design)\s*(?:issue|change|decision)",
            r"refactor\s*(?:to|into|using)",
            r"(?:restructure|reorganize)\s*(?:code|module|package)",
            r"(?:extract|split)\s*(?:class|module|service)",
        ],
        FixCategory.API_CHANGE: [
            r"api\s*(?:change|breaking|compatibility)",
            r"(?:public|external)\s*(?:interface|api)",
            r"(?:signature|parameter)\s*change",
            r"(?:rename|remove)\s*(?:method|function|endpoint)",
        ],
        FixCategory.BREAKING_CHANGE: [
            r"breaking\s*change",
            r"backward[s]?\s*(?:in)?compatibility",
            r"(?:deprecate|remove)\s*(?:support|feature)",
        ],
        FixCategory.DATA_MODEL: [
            r"(?:database|schema|model)\s*(?:change|migration)",
            r"(?:add|remove|modify)\s*(?:field|column|table)",
            r"data\s*(?:model|structure)\s*change",
        ],
        FixCategory.BUSINESS_LOGIC: [
            r"business\s*(?:logic|rule)",
            r"(?:algorithm|calculation)\s*(?:change|update)",
            r"(?:behavior|functionality)\s*change",
        ],
        FixCategory.DEPENDENCY_UPDATE: [
            r"(?:update|upgrade|bump)\s*(?:dependency|package|library)",
            r"(?:major|minor)\s*version\s*(?:update|upgrade)",
        ],
        FixCategory.MULTIPLE_APPROACHES: [
            r"(?:could|might|may)\s*(?:also|alternatively)",
            r"(?:another|different)\s*(?:approach|way|option)",
            r"(?:consider|suggest)\s*(?:using|trying)",
            r"(?:trade-?off|decision|choice)",
        ],
    }

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.6
    AUTO_FIX_THRESHOLD = 0.7  # Minimum confidence to auto-fix

    # Patterns that indicate likely false positives from AI reviewers
    # These suggestions should be validated against actual pipeline results
    FALSE_POSITIVE_PATTERNS = {
        # Version rollback suggestions - often wrong if current version works
        "version_rollback": [
            r"(?:revert|rollback|downgrade)\s*(?:to|back\s*to)\s*v?\d+",
            r"(?:use|switch\s*to)\s*v?\d+\s*instead",
            r"v\d+\s*(?:doesn't|does\s*not)\s*(?:exist|work)",
            r"(?:action|checkout|artifact).*(?:v\d+).*(?:not\s*(?:found|available|exist))",
        ],
        # Claims about non-existent features/actions when they clearly work
        "existence_claims": [
            r"(?:does\s*not|doesn't)\s*(?:exist|work|support)",
            r"(?:not\s*(?:a\s*)?valid|invalid)\s*(?:action|version|syntax)",
            r"(?:no\s*such|unknown)\s*(?:action|command|option)",
        ],
        # Suggestions to fix things that aren't broken
        "fix_working_code": [
            r"(?:this\s*)?(?:will|would|might|could)\s*(?:fail|break|crash)",
            r"(?:won't|will\s*not)\s*(?:work|compile|run)",
        ],
    }

    # Indicators that suggest the pipeline/feature actually works
    PIPELINE_SUCCESS_INDICATORS = [
        "checkout succeeded",
        "artifact uploaded",
        "build passed",
        "tests passed",
        "workflow completed",
        "step succeeded",
        "job completed successfully",
    ]

    def __init__(self, project_owners: Optional[List[str]] = None) -> None:
        """Initialize the agent judgement system.

        Args:
            project_owners: List of usernames who can be asked for guidance
        """
        self.project_owners = project_owners or []

    def _detect_false_positive(self, review_comment: str, context: Optional[dict] = None) -> Tuple[bool, Optional[str]]:
        """Detect if an AI reviewer suggestion is a false positive.

        AI reviewers can make mistakes - suggesting to "fix" things that
        aren't broken, or claiming versions don't exist when they clearly do.
        This method cross-references suggestions against observable reality.

        Args:
            review_comment: The review suggestion to evaluate
            context: Context including pipeline results

        Returns:
            Tuple of (is_false_positive, reason)
        """
        context = context or {}
        comment_lower = review_comment.lower()

        # Check for false positive patterns
        matched_pattern = None
        pattern_type = None
        for fp_type, patterns in self.FALSE_POSITIVE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, comment_lower, re.IGNORECASE):
                    matched_pattern = pattern
                    pattern_type = fp_type
                    break
            if matched_pattern:
                break

        if not matched_pattern:
            return False, None

        # If we found a suspicious pattern, check against reality
        pipeline_status = context.get("pipeline_status", "").lower()
        job_results = context.get("job_results", {})
        recent_commits = context.get("recent_commits", [])

        # Check 1: Did the pipeline actually succeed?
        pipeline_succeeded = any(indicator in pipeline_status for indicator in self.PIPELINE_SUCCESS_INDICATORS)
        if not pipeline_succeeded and job_results:
            # Check individual job results
            pipeline_succeeded = any(result.lower() in ("success", "passed", "completed") for result in job_results.values())

        # Check 2: For version rollback suggestions, check if current version works
        if pattern_type == "version_rollback":
            # Extract the action/version being discussed
            action_match = re.search(r"(checkout|upload-artifact|download-artifact)@v(\d+)", comment_lower)
            if action_match:
                action_name = action_match.group(1)
                # If the checkout/artifact jobs succeeded, this is a false positive
                relevant_jobs = [job for job in job_results if action_name.replace("-", "") in job.lower().replace("-", "")]
                if relevant_jobs and all(job_results.get(job, "").lower() in ("success", "passed") for job in relevant_jobs):
                    return True, (
                        f"Version rollback suggestion is a false positive: {action_name} jobs succeeded with current version"
                    )

            # Check if we recently intentionally updated versions
            version_update_keywords = ["update", "upgrade", "bump", "v6", "v5"]
            if recent_commits and any(
                any(kw in commit.lower() for kw in version_update_keywords) for commit in recent_commits
            ):
                return True, ("Version rollback suggestion contradicts recent intentional version update in commit history")

        # Check 3: For existence claims, verify against pipeline success
        if pattern_type == "existence_claims" and pipeline_succeeded:
            return True, ("Claim about non-existent feature is a false positive: pipeline completed successfully")

        # Check 4: For "will fail" predictions that didn't fail
        if pattern_type == "fix_working_code" and pipeline_succeeded:
            return True, ("Prediction of failure is a false positive: code ran successfully in pipeline")

        # Pattern matched but we couldn't definitively confirm it's wrong
        # Log a warning but don't dismiss - could still be a real issue
        logger.warning(
            f"Suspicious pattern '{pattern_type}' detected but could not "
            f"confirm false positive. Review manually: {review_comment[:100]}..."
        )
        return False, None

    def assess_fix(self, review_comment: str, context: Optional[dict] = None) -> JudgementResult:
        """Assess whether to auto-fix or ask for guidance.

        Args:
            review_comment: The review feedback text to analyze
            context: Optional context dict with keys like:
                - file_path: Path to the file being modified
                - diff: The current PR diff
                - pr_title: PR title
                - is_security_related: Whether PR touches security-sensitive code

        Returns:
            JudgementResult with decision and reasoning
        """
        context = context or {}
        comment_lower = review_comment.lower()

        # FIRST: Check for false positives from AI reviewers
        # AI reviewers can suggest "fixes" for things that aren't broken
        # Cross-reference against observable reality (pipeline results, etc.)
        is_false_positive, dismiss_reason = self._detect_false_positive(review_comment, context)
        if is_false_positive:
            logger.info(f"Dismissing false positive: {dismiss_reason}")
            return JudgementResult(
                should_auto_fix=False,
                confidence=0.0,
                category=FixCategory.FALSE_POSITIVE,
                reasoning=dismiss_reason or "AI reviewer suggestion contradicts observable reality",
                is_false_positive=True,
                dismiss_reason=dismiss_reason,
            )

        # Check high-confidence patterns first
        for category, patterns in self.HIGH_CONFIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, comment_lower, re.IGNORECASE):
                    # Security issues always get highest confidence
                    if category == FixCategory.SECURITY_VULNERABILITY:
                        return JudgementResult(
                            should_auto_fix=True,
                            confidence=0.95,
                            category=category,
                            reasoning=f"Security vulnerability detected: {pattern}. Auto-fixing is critical.",
                        )
                    return JudgementResult(
                        should_auto_fix=True,
                        confidence=self.HIGH_CONFIDENCE_THRESHOLD,
                        category=category,
                        reasoning=f"High-confidence fix category: {category.value}",
                    )

        # Check low-confidence patterns (these take precedence over medium)
        for category, patterns in self.LOW_CONFIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, comment_lower, re.IGNORECASE):
                    question = self._generate_owner_question(category, review_comment, context)
                    return JudgementResult(
                        should_auto_fix=False,
                        confidence=0.3,
                        category=category,
                        reasoning=f"Low-confidence category requiring human decision: {category.value}",
                        ask_owner_question=question,
                    )

        # Check medium-confidence patterns
        for category, patterns in self.MEDIUM_CONFIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, comment_lower, re.IGNORECASE):
                    # For medium confidence, check context for additional signals
                    confidence = self._calculate_medium_confidence(category, context)
                    should_fix = confidence >= self.AUTO_FIX_THRESHOLD

                    if should_fix:
                        return JudgementResult(
                            should_auto_fix=True,
                            confidence=confidence,
                            category=category,
                            reasoning=f"Medium-confidence fix with sufficient context: {category.value}",
                        )
                    question = self._generate_owner_question(category, review_comment, context)
                    return JudgementResult(
                        should_auto_fix=False,
                        confidence=confidence,
                        category=category,
                        reasoning=f"Medium-confidence fix but insufficient context: {category.value}",
                        ask_owner_question=question,
                    )

        # Unknown category - analyze the sentiment and specificity
        confidence, reasoning = self._analyze_unknown_feedback(review_comment, context)
        if confidence >= self.AUTO_FIX_THRESHOLD:
            return JudgementResult(
                should_auto_fix=True,
                confidence=confidence,
                category=FixCategory.UNKNOWN,
                reasoning=reasoning,
            )
        question = self._generate_owner_question(FixCategory.UNKNOWN, review_comment, context)
        return JudgementResult(
            should_auto_fix=False,
            confidence=confidence,
            category=FixCategory.UNKNOWN,
            reasoning=reasoning,
            ask_owner_question=question,
        )

    def _calculate_medium_confidence(self, category: FixCategory, context: dict) -> float:
        """Calculate confidence for medium-confidence categories based on context.

        Args:
            category: The fix category
            context: Additional context

        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = self.MEDIUM_CONFIDENCE_THRESHOLD

        # Boost confidence if we have good context
        if context.get("file_path"):
            base_confidence += 0.05
        if context.get("diff"):
            base_confidence += 0.05
        if context.get("existing_tests"):
            base_confidence += 0.1

        # Reduce confidence for certain risky scenarios
        if context.get("is_security_related"):
            base_confidence -= 0.1
        if context.get("touches_api"):
            base_confidence -= 0.15
        if context.get("touches_database"):
            base_confidence -= 0.15

        # Cap at reasonable bounds
        return max(0.3, min(0.85, base_confidence))

    def _analyze_unknown_feedback(self, review_comment: str, context: dict) -> Tuple[float, str]:
        """Analyze unknown feedback to estimate confidence.

        Args:
            review_comment: The review comment text
            context: Additional context

        Returns:
            Tuple of (confidence, reasoning)
        """
        confidence = 0.5  # Start neutral
        reasons = []

        # Check for specific, actionable language
        if re.search(r"(?:please|should|must|need\s*to)\s+\w+", review_comment, re.IGNORECASE):
            confidence += 0.1
            reasons.append("Contains specific action request")

        # Check for code suggestions
        if "```" in review_comment:
            confidence += 0.15
            reasons.append("Contains code suggestion")

        # Check for file/line references
        if re.search(r"(?:line\s*\d+|file\s*\w+|\w+\.\w+:\d+)", review_comment, re.IGNORECASE):
            confidence += 0.1
            reasons.append("References specific location")

        # Reduce confidence for vague feedback
        if re.search(r"(?:maybe|might|could\s*consider|not\s*sure)", review_comment, re.IGNORECASE):
            confidence -= 0.15
            reasons.append("Contains uncertain language")

        # Reduce confidence for questions
        if review_comment.count("?") > 1:
            confidence -= 0.1
            reasons.append("Contains multiple questions")

        # Adjust based on context
        if context.get("is_draft_pr"):
            confidence -= 0.1
            reasons.append("PR is still in draft")

        confidence = max(0.2, min(0.8, confidence))
        reasoning = "; ".join(reasons) if reasons else "General feedback analysis"

        return confidence, reasoning

    def _generate_owner_question(self, category: FixCategory, review_comment: str, context: dict) -> str:
        """Generate a question to ask the project owner.

        Args:
            category: The fix category
            review_comment: The original review comment
            context: Additional context

        Returns:
            Question string to post as a comment
        """
        # Extract key phrase from review for context
        review_summary = review_comment[:200] + "..." if len(review_comment) > 200 else review_comment

        questions = {
            FixCategory.ARCHITECTURAL: (
                f"This review suggests an architectural change. "
                f"How would you like me to proceed?\n\n"
                f"> {review_summary}\n\n"
                f"Options:\n"
                f"1. Implement the suggested change\n"
                f"2. Keep current approach and explain reasoning\n"
                f"3. Discuss alternative approaches"
            ),
            FixCategory.API_CHANGE: (
                f"This review suggests a change that may affect the API. "
                f"Should I proceed with the modification?\n\n"
                f"> {review_summary}\n\n"
                f"This could affect other parts of the codebase or external consumers."
            ),
            FixCategory.BREAKING_CHANGE: (
                f"This review suggests a potentially breaking change. "
                f"Do you want me to implement this?\n\n"
                f"> {review_summary}\n\n"
                f"Please confirm if backward compatibility is not a concern."
            ),
            FixCategory.DATA_MODEL: (
                f"This review suggests changes to the data model. "
                f"How should I handle this?\n\n"
                f"> {review_summary}\n\n"
                f"This may require database migrations or affect existing data."
            ),
            FixCategory.BUSINESS_LOGIC: (
                f"This review suggests changes to business logic. Can you clarify the expected behavior?\n\n> {review_summary}"
            ),
            FixCategory.DEPENDENCY_UPDATE: (
                f"This review suggests updating dependencies. "
                f"Should I proceed with the update?\n\n"
                f"> {review_summary}\n\n"
                f"This may introduce breaking changes or require additional testing."
            ),
            FixCategory.MULTIPLE_APPROACHES: (
                f"This review presents multiple possible approaches. Which approach would you prefer?\n\n> {review_summary}"
            ),
            FixCategory.UNKNOWN: (
                f"I'm not certain how to best address this feedback. Could you provide guidance?\n\n> {review_summary}"
            ),
        }

        return questions.get(
            category,
            f"I need guidance on this review feedback:\n\n> {review_summary}",
        )

    def should_ask_owner(self, result: JudgementResult) -> bool:
        """Check if we should ask the owner for guidance.

        Args:
            result: The judgement result

        Returns:
            True if we should ask the owner
        """
        # Never ask owner about false positives - dismiss silently
        if result.is_false_positive:
            return False
        return not result.should_auto_fix and result.ask_owner_question is not None

    def should_dismiss(self, result: JudgementResult) -> bool:
        """Check if the suggestion should be dismissed (false positive).

        Args:
            result: The judgement result

        Returns:
            True if the suggestion should be silently dismissed
        """
        return result.is_false_positive
