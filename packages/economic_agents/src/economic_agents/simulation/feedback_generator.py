"""Detailed feedback generation for task submissions."""

import random
from typing import Any, Dict, List, Optional


class FeedbackGenerator:
    """Generates detailed, nuanced feedback for task submissions.

    Replaces binary "approved/rejected" with:
    - Quality scores (performance, style, correctness)
    - Specific improvement suggestions
    - Partial credit for near-success
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize feedback generator.

        Args:
            seed: Random seed for reproducibility
        """
        self.rng = random.Random(seed)

    def generate_task_review(self, task_type: str, base_success_probability: float = 0.8) -> Dict[str, Any]:
        """Generate detailed review for a task submission.

        Args:
            task_type: Type of task (e.g., "ML", "backend", "frontend")
            base_success_probability: Base probability of full success

        Returns:
            Dict with success, quality_scores, feedback, reward_percentage
        """
        # Determine outcome type
        outcome = self._determine_outcome(base_success_probability)

        # Generate quality scores
        quality_scores = self._generate_quality_scores(outcome, task_type)

        # Generate detailed feedback
        feedback = self._generate_feedback(outcome, quality_scores, task_type)

        # Calculate reward percentage
        reward_percentage = self._calculate_reward_percentage(outcome, quality_scores)

        return {
            "success": outcome in ["full_success", "partial_success"],
            "outcome": outcome,
            "quality_scores": quality_scores,
            "feedback": feedback,
            "reward_percentage": reward_percentage,
        }

    def _determine_outcome(self, base_probability: float) -> str:
        """Determine submission outcome.

        Args:
            base_probability: Base probability of success

        Returns:
            Outcome type: full_success, partial_success, minor_issues, or failure
        """
        roll = self.rng.random()

        # Full success (meets all requirements)
        if roll < base_probability * 0.75:
            return "full_success"

        # Partial success (mostly correct, minor issues)
        elif roll < base_probability * 0.95:
            return "partial_success"

        # Minor issues (some correctness problems)
        elif roll < base_probability:
            return "minor_issues"

        # Failure (doesn't meet requirements)
        else:
            return "failure"

    def _generate_quality_scores(self, outcome: str, task_type: str) -> Dict[str, float]:
        """Generate quality scores for different aspects.

        Args:
            outcome: Outcome type
            task_type: Type of task

        Returns:
            Dict with scores for correctness, performance, style, completeness
        """
        base_scores = {
            "full_success": {
                "correctness": (0.9, 1.0),
                "performance": (0.85, 1.0),
                "style": (0.8, 1.0),
                "completeness": (0.95, 1.0),
            },
            "partial_success": {
                "correctness": (0.75, 0.9),
                "performance": (0.7, 0.9),
                "style": (0.6, 0.9),
                "completeness": (0.8, 0.95),
            },
            "minor_issues": {
                "correctness": (0.6, 0.75),
                "performance": (0.5, 0.8),
                "style": (0.5, 0.8),
                "completeness": (0.6, 0.8),
            },
            "failure": {"correctness": (0.2, 0.6), "performance": (0.3, 0.6), "style": (0.4, 0.7), "completeness": (0.3, 0.6)},
        }

        ranges = base_scores[outcome]

        scores = {}
        for aspect, (min_score, max_score) in ranges.items():
            scores[aspect] = self.rng.uniform(min_score, max_score)

        return scores

    def _get_overall_assessment(self, outcome: str) -> str:
        """Get overall assessment message based on outcome."""
        assessments = {
            "full_success": "Excellent work! Your submission meets all requirements.",
            "partial_success": "Good work overall. Your submission meets most requirements with minor issues.",
            "minor_issues": "Your submission has some issues that need to be addressed.",
        }
        return assessments.get(outcome, "Your submission does not meet the requirements and needs significant revision.")

    def _get_score_feedback(self, label: str, score: float, thresholds: List[tuple]) -> str:
        """Get feedback for a score based on thresholds.

        Args:
            label: The score label (e.g., "Correctness")
            score: The actual score value
            thresholds: List of (threshold, message) tuples in descending order

        Returns:
            Formatted feedback string
        """
        for threshold, message in thresholds:
            if score >= threshold:
                return f"\n- {label} ({score:.0%}): {message}"
        # Return the last message if no threshold matched
        return f"\n- {label} ({score:.0%}): {thresholds[-1][1]}"

    def _generate_feedback(self, outcome: str, quality_scores: Dict[str, float], task_type: str) -> str:
        """Generate detailed feedback text.

        Args:
            outcome: Outcome type
            quality_scores: Quality scores dict
            task_type: Type of task

        Returns:
            Detailed feedback string
        """
        feedback_parts = [self._get_overall_assessment(outcome), "\n\nQuality Assessment:"]

        # Define thresholds for each metric
        correctness_thresholds = [
            (0.9, "All test cases pass, logic is sound"),
            (0.75, "Most test cases pass, minor edge case issues"),
            (0.6, "Some test cases fail, logic needs refinement"),
            (0.0, "Multiple test failures, fundamental logic issues"),
        ]

        performance_thresholds = [
            (0.85, "Excellent efficiency, well-optimized"),
            (0.7, "Acceptable performance, minor optimizations possible"),
            (0.5, "Performance issues detected, optimization needed"),
            (0.0, "Significant performance problems, major optimization required"),
        ]

        style_thresholds = [
            (0.8, "Clean, readable, follows best practices"),
            (0.6, "Generally good, some style improvements recommended"),
            (0.5, "Style issues present, refactoring suggested"),
            (0.0, "Poor code quality, significant refactoring needed"),
        ]

        completeness_thresholds = [
            (0.95, "All requirements addressed"),
            (0.8, "Most requirements met, minor gaps"),
            (0.6, "Several requirements missing or incomplete"),
            (0.0, "Major requirements not addressed"),
        ]

        feedback_parts.append(self._get_score_feedback("Correctness", quality_scores["correctness"], correctness_thresholds))
        feedback_parts.append(self._get_score_feedback("Performance", quality_scores["performance"], performance_thresholds))
        feedback_parts.append(self._get_score_feedback("Code Style", quality_scores["style"], style_thresholds))
        feedback_parts.append(
            self._get_score_feedback("Completeness", quality_scores["completeness"], completeness_thresholds)
        )

        suggestions = self._generate_improvement_suggestions(quality_scores, task_type)
        if suggestions:
            feedback_parts.append("\n\nSuggestions for improvement:")
            for suggestion in suggestions:
                feedback_parts.append(f"\n- {suggestion}")

        return "".join(feedback_parts)

    def _generate_improvement_suggestions(self, quality_scores: Dict[str, float], task_type: str) -> List[str]:
        """Generate specific improvement suggestions based on weak areas.

        Args:
            quality_scores: Quality scores dict
            task_type: Type of task

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Correctness suggestions
        if quality_scores["correctness"] < 0.75:
            suggestions.append("Review the logic for edge cases (empty inputs, boundary values)")
            if task_type == "ML":
                suggestions.append("Verify model predictions match expected outputs")
            elif task_type == "backend":
                suggestions.append("Check error handling for invalid inputs")
            elif task_type == "frontend":
                suggestions.append("Test UI interactions thoroughly")

        # Performance suggestions
        if quality_scores["performance"] < 0.7:
            if task_type == "ML":
                suggestions.append("Consider vectorization or batch processing for better performance")
            elif task_type == "backend":
                suggestions.append("Look for opportunities to reduce database queries or API calls")
            else:
                suggestions.append("Profile the code to identify bottlenecks")

        # Style suggestions
        if quality_scores["style"] < 0.6:
            suggestions.append("Add docstrings to functions and classes")
            suggestions.append("Follow PEP 8 style guidelines (or language-appropriate standards)")
            suggestions.append("Extract magic numbers into named constants")

        # Completeness suggestions
        if quality_scores["completeness"] < 0.8:
            suggestions.append("Review requirements to ensure all features are implemented")
            suggestions.append("Add missing error handling")
            if task_type == "ML":
                suggestions.append("Include model evaluation metrics")

        # General suggestions if code is generally good
        if not suggestions and quality_scores["correctness"] >= 0.75:
            suggestions.append("Consider adding type hints for better code clarity")
            suggestions.append("Add more inline comments for complex logic")

        return suggestions

    def _calculate_reward_percentage(self, outcome: str, quality_scores: Dict[str, float]) -> float:
        """Calculate what percentage of reward should be paid.

        Args:
            outcome: Outcome type
            quality_scores: Quality scores dict

        Returns:
            Percentage of full reward to pay (0.0-1.0)
        """
        if outcome == "full_success":
            # Full reward with potential bonus for exceptional quality
            avg_score = sum(quality_scores.values()) / len(quality_scores)
            if avg_score >= 0.95:
                return 1.0  # Full reward
            else:
                return min(1.0, avg_score * 1.05)  # Slight boost

        elif outcome == "partial_success":
            # Partial reward based on quality scores
            avg_score = sum(quality_scores.values()) / len(quality_scores)
            return max(0.6, min(0.9, avg_score))

        elif outcome == "minor_issues":
            # Reduced reward
            avg_score = sum(quality_scores.values()) / len(quality_scores)
            return max(0.3, min(0.6, avg_score * 0.8))

        else:  # failure
            # No reward
            return 0.0

    def generate_quick_feedback(self, success: bool, quality_percentage: float) -> str:
        """Generate quick feedback for simple pass/fail scenarios.

        Args:
            success: Whether submission succeeded
            quality_percentage: Overall quality (0.0-1.0)

        Returns:
            Quick feedback string
        """
        if success:
            if quality_percentage >= 0.95:
                return f"Outstanding work! Quality: {quality_percentage:.0%}. All requirements exceeded."
            elif quality_percentage >= 0.85:
                return f"Great work! Quality: {quality_percentage:.0%}. Meets all requirements."
            else:
                return f"Good work. Quality: {quality_percentage:.0%}. Minor improvements possible."
        else:
            if quality_percentage >= 0.5:
                return f"Close! Quality: {quality_percentage:.0%}. Please address feedback and resubmit."
            else:
                return f"Needs work. Quality: {quality_percentage:.0%}. Significant revision required."
