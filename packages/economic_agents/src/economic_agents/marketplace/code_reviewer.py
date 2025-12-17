"""Code reviewer using Claude Code for autonomous code review."""

import json
import logging
from pathlib import Path
import tempfile
from typing import Any, Dict

from economic_agents.agent.llm.executors.claude import ClaudeExecutor

logger = logging.getLogger(__name__)


class CodeReviewer:
    """Reviews code submissions using Claude Code and automated testing."""

    def __init__(self, config: dict | None = None):
        """Initialize code reviewer.

        Args:
            config: Configuration dict for Claude executor
        """
        self.executor = ClaudeExecutor(config)

    def review_submission(self, task: Dict, code: str, timeout: int = 300) -> Dict:
        """Review a code submission.

        Args:
            task: Original task with requirements
            code: Submitted code
            timeout: Review timeout in seconds

        Returns:
            dict with:
                - approved: bool
                - score: float (0.0 to 1.0)
                - feedback: str
                - test_results: dict
        """
        task_id = task.get("id", "unknown")
        requirements = task.get("requirements", {})

        logger.info("Reviewing submission for task %s", task_id)

        # First, run automated tests
        test_results = self._run_tests(code, requirements)

        # Then, get Claude's review
        claude_review = self._get_claude_review(task, code, test_results, timeout)

        # Combine test results and Claude's review
        all_tests_passed = test_results.get("all_passed", False)
        claude_approved = claude_review.get("approved", False)

        # Approval requires both passing tests AND Claude's approval
        approved = all_tests_passed and claude_approved

        return {
            "approved": approved,
            "score": claude_review.get("score", 0.0) if all_tests_passed else 0.0,
            "feedback": self._build_feedback(test_results, claude_review),
            "test_results": test_results,
            "claude_review": claude_review,
        }

    def _run_tests(self, code: str, requirements: Dict) -> Dict:
        """Run automated tests on submitted code.

        Args:
            code: Submitted code
            requirements: Task requirements with tests

        Returns:
            Test results dict
        """
        function_name = requirements.get("function_name", "solution")
        tests = requirements.get("tests", [])

        if not tests:
            return {"all_passed": True, "passed": 0, "failed": 0, "results": []}

        # Create temp file with the code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            code_file = f.name

        try:
            results = []
            passed = 0
            failed = 0

            for i, test in enumerate(tests, 1):
                test_input = test.get("input")
                expected = test.get("expected")

                try:
                    # Import the function
                    import importlib.util

                    spec = importlib.util.spec_from_file_location("solution", code_file)
                    if spec is None or spec.loader is None:
                        raise RuntimeError("Failed to load module spec")

                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    func = getattr(module, function_name)

                    # Run test
                    if isinstance(test_input, tuple):
                        actual = func(*test_input)
                    else:
                        actual = func(test_input)

                    # Check result
                    test_passed = actual == expected

                    results.append(
                        {
                            "test_num": i,
                            "passed": test_passed,
                            "input": str(test_input),
                            "expected": str(expected),
                            "actual": str(actual),
                        }
                    )

                    if test_passed:
                        passed += 1
                    else:
                        failed += 1

                except Exception as e:
                    results.append(
                        {
                            "test_num": i,
                            "passed": False,
                            "input": str(test_input),
                            "expected": str(expected),
                            "actual": f"ERROR: {str(e)}",
                        }
                    )
                    failed += 1

            return {
                "all_passed": failed == 0,
                "passed": passed,
                "failed": failed,
                "total": len(tests),
                "results": results,
            }

        finally:
            # Clean up temp file
            Path(code_file).unlink(missing_ok=True)

    def _get_claude_review(self, task: Dict, code: str, test_results: Dict, timeout: int) -> Dict:
        """Get Claude's review of the code.

        Args:
            task: Original task
            code: Submitted code
            test_results: Automated test results
            timeout: Timeout in seconds

        Returns:
            Review dict with approved, score, and comments
        """
        prompt = self._build_review_prompt(task, code, test_results)

        try:
            response = self.executor.execute(prompt, timeout=timeout)

            # Parse Claude's review
            review = self._parse_review(response)

            logger.info("Claude review: approved=%s, score=%s", review.get("approved"), review.get("score"))

            return review

        except Exception as e:
            logger.error("Claude review failed: %s", e)
            return {"approved": False, "score": 0.0, "comments": f"Review failed: {str(e)}"}

    def _build_review_prompt(self, task: Dict, code: str, test_results: Dict) -> str:
        """Build review prompt for Claude.

        Args:
            task: Task dict
            code: Submitted code
            test_results: Test results

        Returns:
            Review prompt
        """
        title = task.get("title", "Coding Task")
        requirements = task.get("requirements", {})
        spec = requirements.get("spec", "")

        tests_passed = test_results.get("all_passed", False)
        test_summary = f"Tests: {test_results.get('passed', 0)}/{test_results.get('total', 0)} passed"

        prompt = f"""You are reviewing a code submission for a coding task.

TASK: {title}

REQUIREMENTS:
{spec}

SUBMITTED CODE:
```python
{code}
```

AUTOMATED TEST RESULTS:
{test_summary}
Tests passed: {tests_passed}

Test details:
"""

        for result in test_results.get("results", []):
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            prompt += f"""
{status} Test {result["test_num"]}:
  Input: {result["input"]}
  Expected: {result["expected"]}
  Actual: {result["actual"]}
"""

        prompt += """

REVIEW CRITERIA:
1. Code correctness (does it solve the problem?)
2. Code quality (clean, readable, well-structured?)
3. Follows requirements (uses correct function name, parameters?)
4. Edge case handling
5. Documentation (docstring present and clear?)

Provide your review in this EXACT JSON format (no markdown, no code blocks):

{
  "approved": true/false,
  "score": 0.0-1.0,
  "comments": "detailed feedback here"
}

Output ONLY the JSON object, nothing else.
"""

        return prompt

    def _parse_review(self, response: str) -> Dict[str, Any]:
        """Parse Claude's review response.

        Args:
            response: Claude's response

        Returns:
            Parsed review dict
        """
        # Extract JSON from response
        response = response.strip()

        try:
            # Try direct parse
            review: Dict[str, Any] = json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON in response
            if "{" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
                review = json.loads(json_str)
            else:
                # Fallback
                return {"approved": False, "score": 0.0, "comments": "Failed to parse review"}

        return review

    def _build_feedback(self, test_results: Dict, claude_review: Dict) -> str:
        """Build combined feedback message.

        Args:
            test_results: Test results
            claude_review: Claude's review

        Returns:
            Feedback string
        """
        feedback = []

        # Test results
        if test_results.get("all_passed"):
            feedback.append(f"✓ All {test_results['total']} tests passed!")
        else:
            feedback.append(
                f"✗ Tests: {test_results['passed']}/{test_results['total']} passed, {test_results['failed']} failed"
            )

        # Claude's comments
        feedback.append(f"\nReviewer Comments:\n{claude_review.get('comments', 'No comments')}")

        # Score
        score = claude_review.get("score", 0.0)
        feedback.append(f"\nQuality Score: {score:.1%}")

        return "\n".join(feedback)
