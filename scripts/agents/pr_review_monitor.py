#!/usr/bin/env python3
"""
PR Review Monitoring Agent

This agent monitors pull request reviews (especially from Gemini) and:
1. Analyzes review feedback
2. Implements requested changes
3. Comments when changes are addressed
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from logging_security import get_secure_logger, setup_secure_logging
from security import SecurityManager
from utils import get_github_token, run_gh_command

# Configure logging with security
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
setup_secure_logging()
logger = get_secure_logger(__name__)


class PRReviewMonitor:
    """Monitor PR reviews and address feedback automatically."""

    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        if not self.repo:
            logger.error("GITHUB_REPOSITORY environment variable is required but not set")
            raise RuntimeError("GITHUB_REPOSITORY environment variable must be set")
        self.token = get_github_token()

        # Safety control - auto-fixing is enabled when AI agents are enabled
        self.auto_fix_enabled = os.environ.get("ENABLE_AI_AGENTS", "false").lower() == "true"

        # Enable verbose logging
        self.verbose = os.environ.get("PR_MONITOR_VERBOSE", "false").lower() == "true"
        if self.verbose:
            logger.info("Verbose logging enabled")

        # Load configuration
        self.config = self._load_config()
        pr_config = self.config.get("agents", {}).get("pr_review_monitor", {})

        # Use config values with fallbacks
        self.review_bot_names = pr_config.get("review_bot_names", ["gemini-bot", "github-actions[bot]", "dependabot[bot]"])
        self.auto_fix_threshold = pr_config.get("auto_fix_threshold", {"critical_issues": 0, "total_issues": 5})
        # Cutoff period in hours for filtering recent PRs
        self.cutoff_hours = pr_config.get("cutoff_hours", 24)
        # Required labels for PR processing
        self.required_labels = pr_config.get("required_labels", ["help wanted"])

        self.agent_tag = "[AI Agent]"
        self.security_manager = SecurityManager()

        # Load secrets to mask from environment
        self._load_mask_config()

    def _load_mask_config(self) -> None:
        """Load masking configuration from environment."""
        # Get list of environment variables to mask from workflow
        mask_vars = os.environ.get("MASK_ENV_VARS", "")
        if mask_vars:
            self.env_vars_to_mask = [v.strip() for v in mask_vars.split(",") if v.strip()]
        else:
            # Default list if not specified
            self.env_vars_to_mask = [
                "GITHUB_TOKEN",
                "ANTHROPIC_API_KEY",
                "AI_AGENT_TOKEN",
            ]

        # Auto-detect additional sensitive environment variables
        sensitive_prefixes = [
            "SECRET_",
            "TOKEN_",
            "API_",
            "KEY_",
            "PASSWORD_",
            "PRIVATE_",
        ]
        sensitive_suffixes = [
            "_SECRET",
            "_TOKEN",
            "_API_KEY",
            "_KEY",
            "_PASSWORD",
            "_PRIVATE_KEY",
        ]

        for var_name in os.environ:
            # Check if variable name suggests it's sensitive
            if any(var_name.startswith(prefix) for prefix in sensitive_prefixes) or any(
                var_name.endswith(suffix) for suffix in sensitive_suffixes
            ):
                if var_name not in self.env_vars_to_mask:
                    self.env_vars_to_mask.append(var_name)
                    logger.debug(f"Auto-detected sensitive variable: {var_name}")

        # Build patterns for masking
        self.secret_patterns = []

        # Add patterns for each environment variable's value
        for var_name in self.env_vars_to_mask:
            var_value = os.environ.get(var_name)
            if var_value and len(var_value) > 10:  # Only mask if it's a substantial value
                # Escape special regex characters
                escaped_value = re.escape(var_value)
                self.secret_patterns.append((escaped_value, f"[{var_name}]"))

        # Always include common secret patterns
        self.secret_patterns.extend(
            [
                # GitHub tokens
                (r"ghp_[a-zA-Z0-9]{36}", "[GITHUB_TOKEN]"),
                (r"ghs_[a-zA-Z0-9]{36}", "[GITHUB_SECRET]"),
                (r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}", "[GITHUB_PAT]"),
                # API keys
                (r"sk-[a-zA-Z0-9]{48}", "[API_KEY]"),
                (r"Bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer [REDACTED]"),
                # URLs with credentials
                (r"https?://[^:]+:[^@]+@[^\s]+", "https://[REDACTED]@[URL]"),
            ]
        )

        logger.info(f"Configured to mask {len(self.env_vars_to_mask)} environment variables")

    def mask_secrets(self, text: str) -> str:
        """Mask secrets in text based on configured patterns."""
        if not text:
            return text

        masked_text = text

        # Apply all masking patterns
        for pattern, replacement in self.secret_patterns:
            try:
                masked_text = re.sub(pattern, replacement, masked_text, flags=re.IGNORECASE)
            except re.error:
                # Skip invalid patterns
                continue

        return masked_text

    def _load_config(self) -> dict:
        """Load configuration from config.json."""
        config_path = Path(__file__).parent / "config.json"
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load config from {config_path}: {e}")
            return {}

    def get_open_prs(self) -> List[Dict]:
        """Get open pull requests, filtered by recent activity."""
        # Check if we should target a specific PR
        target_pr = os.environ.get("TARGET_PR_NUMBER")

        if target_pr:
            logger.info(f"Targeting specific PR #{target_pr}")
            output = run_gh_command(
                [
                    "pr",
                    "view",
                    target_pr,
                    "--repo",
                    self.repo,
                    "--json",
                    "number,title,body,author,createdAt,updatedAt,labels,headRefName",
                ]
            )
            if output:
                try:
                    pr_data = json.loads(output)
                    # Wrap in list for consistent processing
                    all_prs = [pr_data]
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse PR JSON: {e}")
                    return []
            else:
                return []
        else:
            output = run_gh_command(
                [
                    "pr",
                    "list",
                    "--repo",
                    self.repo,
                    "--state",
                    "open",
                    "--json",
                    "number,title,body,author,createdAt,updatedAt,labels,headRefName",
                ]
            )

        if output:
            try:
                all_prs = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse PRs JSON: {e}")
                return []

            # Filter by recent activity
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.cutoff_hours)
            recent_prs = []

            for pr in all_prs:
                # Check both created and updated times
                created_at = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
                updated_at = (
                    datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00")) if "updatedAt" in pr else created_at
                )

                # Include PR if it was created or updated recently
                if created_at >= cutoff_time or updated_at >= cutoff_time:
                    recent_prs.append(pr)

            logger.info(f"Filtered {len(all_prs)} PRs to {len(recent_prs)} recent PRs (cutoff: {self.cutoff_hours} hours)")
            return recent_prs
        return []

    def get_pr_reviews(self, pr_number: int) -> List[Dict]:
        """Get all reviews for a specific PR."""
        output = run_gh_command(["pr", "view", str(pr_number), "--repo", self.repo, "--json", "reviews"])

        if output:
            try:
                data = json.loads(output)
                return data.get("reviews", [])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse reviews JSON: {e}")
                return []
        return []

    def get_pr_review_comments(self, pr_number: int) -> List[Dict]:
        """Get all review comments for a specific PR."""
        output = run_gh_command(["api", f"/repos/{self.repo}/pulls/{pr_number}/comments", "--paginate"])

        if output:
            try:
                return json.loads(output) if output.startswith("[") else [json.loads(output)]
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse comments JSON: {e}")
                return []
        return []

    def get_pr_general_comments(self, pr_number: int) -> List[Dict]:
        """Get all general comments for a specific PR (including Gemini bot reviews)."""
        output = run_gh_command(["api", f"/repos/{self.repo}/issues/{pr_number}/comments", "--paginate"])

        if output:
            try:
                return json.loads(output) if output.startswith("[") else [json.loads(output)]
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse general comments JSON: {e}")
                return []
        return []

    def get_pr_check_status(self, pr_number: int) -> Dict:
        """Get the status of checks for a PR."""
        # Get PR status check rollup which includes all checks
        pr_output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "statusCheckRollup",
            ]
        )

        if not pr_output:
            logger.error(f"Failed to get PR #{pr_number} details")
            return {
                "checks": [],
                "has_failures": False,
                "failing_checks": [],
                "in_progress": False,
            }

        try:
            pr_data = json.loads(pr_output)
            status_rollup = pr_data.get("statusCheckRollup", [])

            # If no status checks, return empty
            if not status_rollup:
                logger.info(f"PR #{pr_number}: No status checks found")
                return {
                    "checks": [],
                    "has_failures": False,
                    "failing_checks": [],
                    "in_progress": False,
                }

            # Process status checks
            all_checks = []
            failing_checks = []
            in_progress_checks = []

            for check in status_rollup:
                all_checks.append(check)

                # GitHub uses different status values in statusCheckRollup
                status = check.get("status", "").upper()
                conclusion = check.get("conclusion", "").upper() if check.get("conclusion") else None

                logger.debug(f"Check: {check.get('name')} - Status: {status} - Conclusion: {conclusion}")

                # Check if still in progress
                if status in ["PENDING", "QUEUED", "IN_PROGRESS"]:
                    in_progress_checks.append(check)
                # Check if failed
                elif conclusion in [
                    "FAILURE",
                    "CANCELLED",
                    "TIMED_OUT",
                    "ACTION_REQUIRED",
                ]:
                    failing_checks.append(check)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse PR data: {e}")
            return {
                "checks": [],
                "has_failures": False,
                "failing_checks": [],
                "in_progress": False,
            }
        except Exception as e:
            logger.error(f"Error processing check status: {e}")
            return {
                "checks": [],
                "has_failures": False,
                "failing_checks": [],
                "in_progress": False,
            }

        # Log summary
        logger.info(f"PR #{pr_number}: Found {len(all_checks)} total checks")
        if in_progress_checks:
            logger.info(f"PR #{pr_number}: {len(in_progress_checks)} checks still in progress")
        if failing_checks:
            logger.info(f"PR #{pr_number}: {len(failing_checks)} checks failed")

        return {
            "checks": all_checks,
            "has_failures": len(failing_checks) > 0,
            "failing_checks": failing_checks,
            "in_progress": len(in_progress_checks) > 0,
        }

    def get_check_run_logs(self, pr_number: int, check_name: str) -> str:
        """Get the logs for a specific check run."""
        # First get the check runs for the PR
        output = run_gh_command(["api", f"/repos/{self.repo}/pulls/{pr_number}", "--jq", ".head.sha"])

        if not output:
            return ""

        commit_sha = output.strip()

        # Get check runs for this commit
        output = run_gh_command(["api", f"/repos/{self.repo}/commits/{commit_sha}/check-runs"])

        if output:
            try:
                data = json.loads(output)
                check_runs = data.get("check_runs", [])

                # Find the check run by name
                for run in check_runs:
                    if run.get("name") == check_name:
                        run_id = run.get("id")
                        # Get the logs for this run
                        log_output = run_gh_command(
                            [
                                "api",
                                f"/repos/{self.repo}/actions/runs/{run_id}/logs",
                                "-i",
                            ]
                        )
                        return log_output or f"Could not fetch logs for {check_name}"

                return f"Check run not found: {check_name}"
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse check runs JSON: {e}")
                return ""
        return ""

    def has_agent_addressed_review(self, pr_number: int) -> bool:
        """Check if agent has already addressed the review."""
        output = run_gh_command(["pr", "view", str(pr_number), "--repo", self.repo, "--json", "comments"])

        if output:
            try:
                data = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse comment data JSON: {e}")
                return False
            for comment in data.get("comments", []):
                if self.agent_tag in comment.get("body", "") and "addressed" in comment.get("body", "").lower():
                    return True
        return False

    def has_agent_attempted_pipeline_fix(self, pr_number: int) -> bool:
        """Check if agent has already attempted to fix pipeline failures."""
        output = run_gh_command(["pr", "view", str(pr_number), "--repo", self.repo, "--json", "comments"])

        if output:
            try:
                data = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse comment data JSON: {e}")
                return False
            for comment in data.get("comments", []):
                if (
                    self.agent_tag in comment.get("body", "")
                    and "pipeline" in comment.get("body", "").lower()
                    and any(word in comment.get("body", "").lower() for word in ["fixing", "fixed", "attempted"])
                ):
                    return True
        return False

    def parse_review_feedback(
        self,
        reviews: List[Dict],
        review_comments: List[Dict],
        general_comments: List[Dict],
    ) -> Dict:
        """Parse review feedback to extract actionable items."""
        feedback = {
            "changes_requested": False,
            "issues": [],
            "suggestions": [],
            "must_fix": [],
            "nice_to_have": [],
        }

        # Check review states
        for review in reviews:
            if review.get("state") == "CHANGES_REQUESTED":
                feedback["changes_requested"] = True

            body = review.get("body", "")

            # Extract issues and suggestions using patterns
            issue_patterns = [
                r"(?:issue|problem|error|bug):\s*(.+?)(?:\n|$)",
                r"(?:must fix|required|critical):\s*(.+?)(?:\n|$)",
                r"❌\s*(.+?)(?:\n|$)",
                r"🔴\s*(.+?)(?:\n|$)",
            ]

            suggestion_patterns = [
                r"(?:suggestion|consider|recommend):\s*(.+?)(?:\n|$)",
                r"(?:nice to have|optional):\s*(.+?)(?:\n|$)",
                r"💡\s*(.+?)(?:\n|$)",
                r"ℹ️\s*(.+?)(?:\n|$)",
            ]

            for pattern in issue_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE | re.MULTILINE)
                feedback["must_fix"].extend(matches)

            for pattern in suggestion_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE | re.MULTILINE)
                feedback["nice_to_have"].extend(matches)

        # Parse review comments (inline code comments)
        for comment in review_comments:
            if comment.get("author", {}).get("login") in self.review_bot_names:
                path = comment.get("path", "")
                line = comment.get("line", 0)
                body = comment.get("body", "")

                feedback["issues"].append(
                    {
                        "file": path,
                        "line": line,
                        "comment": body,
                        "severity": (
                            "high" if any(word in body.lower() for word in ["error", "bug", "critical", "must"]) else "medium"
                        ),
                    }
                )

        # Parse general PR comments (where Gemini posts its reviews)
        for comment in general_comments:
            author = comment.get("user", {}).get("login", "")
            if author in self.review_bot_names or author == "github-actions":
                body = comment.get("body", "")

                # Look for review patterns in general comments
                if any(
                    phrase in body.lower()
                    for phrase in [
                        "review:",
                        "feedback:",
                        "found",
                        "issue",
                        "error",
                        "suggestion",
                    ]
                ):
                    # Extract issues from Gemini's structured reviews
                    issue_patterns = [
                        r"(?:issue|problem|error|bug):\s*(.+?)(?:\n|$)",
                        r"(?:must fix|required|critical):\s*(.+?)(?:\n|$)",
                        r"❌\s*(.+?)(?:\n|$)",
                        r"🔴\s*(.+?)(?:\n|$)",
                        r"\*\*Issue\*\*:\s*(.+?)(?:\n|$)",
                        r"\*\*Error\*\*:\s*(.+?)(?:\n|$)",
                    ]

                    for pattern in issue_patterns:
                        matches = re.findall(pattern, body, re.IGNORECASE | re.MULTILINE)
                        feedback["must_fix"].extend(matches)

                    # Also look for code blocks with issues
                    code_block_pattern = r"```[^\n]*\n(.*?)\n```"
                    code_blocks = re.findall(code_block_pattern, body, re.DOTALL)
                    if code_blocks and any(word in body.lower() for word in ["error", "issue", "problem"]):
                        for block in code_blocks:
                            feedback["issues"].append(
                                {
                                    "file": "See PR comment",
                                    "line": 0,
                                    "comment": f"Code issue: {block[:200]}...",
                                    "severity": "high",
                                }
                            )

        return feedback

    def prepare_feedback_text(self, feedback: Dict) -> tuple:
        """Prepare feedback text for the fix script."""
        issues_text = "\n".join(
            [f"- File: {issue['file']}, Line: {issue['line']}, Issue: {issue['comment']}" for issue in feedback["issues"]]
        )
        must_fix_text = "\n".join([f"- {fix}" for fix in feedback["must_fix"]])
        suggestions_text = "\n".join([f"- {suggestion}" for suggestion in feedback["nice_to_have"]])

        return must_fix_text, issues_text, suggestions_text

    def parse_pipeline_failures(self, failing_checks: List[Dict]) -> Dict:
        """Parse pipeline failure information."""
        failures = {
            "lint_failures": [],
            "test_failures": [],
            "build_failures": [],
            "other_failures": [],
            "total_failures": len(failing_checks),
        }

        for check in failing_checks:
            check_name = (check.get("name") or check.get("context", "Unknown")).lower()
            failure_info = {
                "name": check.get("name") or check.get("context", "Unknown"),
                "url": check.get("detailsUrl") or check.get("targetUrl", ""),
                "status": check.get("status", ""),
                "conclusion": check.get("conclusion", ""),
            }

            if any(word in check_name for word in ["lint", "format", "flake", "black", "mypy"]):
                failures["lint_failures"].append(failure_info)
            elif any(word in check_name for word in ["test", "pytest", "unittest"]):
                failures["test_failures"].append(failure_info)
            elif any(word in check_name for word in ["build", "compile", "docker"]):
                failures["build_failures"].append(failure_info)
            else:
                failures["other_failures"].append(failure_info)

        return failures

    def address_review_feedback(
        self, pr_number: int, branch_name: str, feedback: Dict
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Implement changes to address review feedback. Returns (success, error_details, agent_output)"""
        # Check if auto-fix is enabled
        if not self.auto_fix_enabled:
            logger.info(f"AI agents are disabled. Skipping automatic fixes for PR #{pr_number}")
            logger.info("To enable auto-fix, set ENABLE_AI_AGENTS=true environment variable")
            return False, "AI agents are disabled", None

        # Add safety checks
        total_issues = len(feedback["must_fix"]) + len(feedback["issues"])
        if total_issues > 20:
            logger.warning(f"Too many issues ({total_issues}) for automatic fixing. Skipping auto-fix.")
            return False, f"Too many issues ({total_issues}) for automatic fixing", None

        # Prepare feedback text
        must_fix_text, issues_text, suggestions_text = self.prepare_feedback_text(feedback)

        # Use the external script
        script_path = Path(__file__).parent / "templates" / "fix_pr_review.sh"
        if not script_path.exists():
            logger.error(f"Fix script not found at {script_path}")
            return False, f"Fix script not found at {script_path}", None

        try:
            # Pass sensitive data via stdin instead of command-line arguments
            feedback_data = {
                "must_fix": must_fix_text,
                "issues": issues_text,
                "suggestions": suggestions_text,
            }

            # Pass environment variables including GITHUB_TOKEN
            env = os.environ.copy()

            if self.verbose:
                logger.info(f"Running fix script for PR #{pr_number} on branch {branch_name}")
                logger.info(f"Total issues to fix: {total_issues}")

            result = subprocess.run(
                [
                    str(script_path),
                    str(pr_number),
                    branch_name,
                ],
                input=json.dumps(feedback_data),
                text=True,
                check=True,
                timeout=300,  # 5 minute timeout
                env=env,
                capture_output=True,
            )

            # Capture agent output for logging
            agent_output = result.stdout if result.stdout else ""
            if self.verbose and agent_output:
                logger.info(f"Agent output:\n{agent_output[:1000]}...")  # Log first 1000 chars

            logger.info(f"Successfully addressed feedback for PR #{pr_number}")
            return True, None, agent_output
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while addressing feedback for PR #{pr_number}")
            return False, "Operation timed out after 5 minutes", None
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to address feedback for PR #{pr_number}: {e}")
            # Capture detailed error information
            error_details = f"Exit code: {e.returncode}\n"
            agent_output = ""
            if e.stdout:
                agent_output = e.stdout
                # Show more output for debugging push issues
                error_details += f"\nOutput:\n{e.stdout[-4000:]}"  # Last 4000 chars
            if e.stderr:
                # Filter out Git LFS warnings which are not actual errors
                stderr_lines = e.stderr.splitlines()
                filtered_stderr = "\n".join(line for line in stderr_lines if "Git LFS" not in line and "git-lfs" not in line)
                if filtered_stderr.strip():
                    error_details += f"\nError:\n{filtered_stderr[-4000:]}"  # Last 4000 chars
            return False, error_details, agent_output

    def address_pipeline_failures(
        self, pr_number: int, branch_name: str, failures: Dict
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Attempt to fix pipeline failures. Returns (success, error_details, agent_output)"""
        # Check if auto-fix is enabled
        if not self.auto_fix_enabled:
            logger.info(f"AI agents are disabled. Skipping automatic pipeline fixes for PR #{pr_number}")
            return False, "AI agents are disabled", None

        # Safety check - don't try to fix too many failures at once
        if failures["total_failures"] > 10:
            logger.warning(
                f"Too many failures ({failures['total_failures']}) for automatic fixing. Manual intervention required."
            )
            return (
                False,
                f"Too many failures ({failures['total_failures']}) for automatic fixing",
                None,
            )

        # Use the external script for pipeline fixes
        script_path = Path(__file__).parent / "templates" / "fix_pipeline_failure.sh"
        if not script_path.exists():
            logger.error(f"Pipeline fix script not found at {script_path}")
            return False, f"Pipeline fix script not found at {script_path}", None

        try:
            # Prepare failure information
            failure_data = {
                "lint_failures": [f["name"] for f in failures["lint_failures"]],
                "test_failures": [f["name"] for f in failures["test_failures"]],
                "build_failures": [f["name"] for f in failures["build_failures"]],
                "other_failures": [f["name"] for f in failures["other_failures"]],
            }

            # Pass environment variables including GITHUB_TOKEN
            env = os.environ.copy()

            if self.verbose:
                logger.info(f"Running pipeline fix script for PR #{pr_number} on branch {branch_name}")
                logger.info(f"Failures to fix: {failures['total_failures']}")

            result = subprocess.run(
                [
                    str(script_path),
                    str(pr_number),
                    branch_name,
                ],
                input=json.dumps(failure_data),
                text=True,
                check=True,
                timeout=600,  # 10 minute timeout for pipeline fixes
                env=env,
                capture_output=True,
            )

            # Capture agent output for logging
            agent_output = result.stdout if result.stdout else ""
            if self.verbose and agent_output:
                logger.info(f"Agent output:\n{agent_output[:1000]}...")  # Log first 1000 chars

            logger.info(f"Successfully fixed pipeline failures for PR #{pr_number}")
            return True, None, agent_output
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while fixing pipeline failures for PR #{pr_number}")
            return False, "Operation timed out after 10 minutes", None
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to fix pipeline failures for PR #{pr_number}: {e}")
            # Capture detailed error information
            error_details = f"Exit code: {e.returncode}\n"
            agent_output = ""
            if e.stdout:
                agent_output = e.stdout
                # Show more output for debugging push issues
                error_details += f"\nOutput:\n{e.stdout[-4000:]}"  # Last 4000 chars
            if e.stderr:
                # Filter out Git LFS warnings which are not actual errors
                stderr_lines = e.stderr.splitlines()
                filtered_stderr = "\n".join(line for line in stderr_lines if "Git LFS" not in line and "git-lfs" not in line)
                if filtered_stderr.strip():
                    error_details += f"\nError:\n{filtered_stderr[-4000:]}"  # Last 4000 chars
            return False, error_details, agent_output

    def post_completion_comment(
        self,
        pr_number: int,
        feedback: Dict,
        success: bool,
        error_details: Optional[str] = None,
        agent_output: Optional[str] = None,
    ) -> None:
        """Post a comment indicating review feedback has been addressed."""
        if success:
            comment_body = f"""{self.agent_tag} I've reviewed and addressed the feedback from the PR review:

✅ **Changes Made:**
- Addressed {len(feedback['must_fix'])} critical issues
- Fixed {len(feedback['issues'])} inline code comments
- Implemented {len(feedback['nice_to_have'])} suggested improvements

All requested changes have been implemented and tests are passing. The PR is ready for another review.
"""

            # Add agent work details if verbose mode is enabled
            if self.verbose and agent_output:
                # Extract key information from agent output
                masked_output = self.mask_secrets(agent_output)

                # Look for specific sections in the output
                work_summary = []

                # Extract Claude's response (between specific markers)
                if "Running Claude to address review feedback..." in masked_output:
                    claude_section = masked_output.split("Running Claude to address review feedback...")[1]
                    if "Running tests..." in claude_section:
                        claude_work = claude_section.split("Running tests...")[0].strip()
                        if claude_work and len(claude_work) > 100:  # Only include if substantial
                            work_summary.append("**Claude's Analysis:**")
                            work_summary.append("```")
                            work_summary.append(claude_work[:1500] + ("..." if len(claude_work) > 1500 else ""))
                            work_summary.append("```")

                # Extract test results
                if "Running tests..." in masked_output:
                    test_section = masked_output.split("Running tests...")[1]
                    if "Committing changes..." in test_section:
                        test_results = test_section.split("Committing changes...")[0].strip()
                        if test_results:
                            work_summary.append("\n**Test Results:**")
                            work_summary.append("```")
                            work_summary.append(test_results[:500] + ("..." if len(test_results) > 500 else ""))
                            work_summary.append("```")

                # Extract commit info
                if "Committing changes..." in masked_output and "git add -A" in masked_output:
                    commit_section = masked_output.split("Committing changes...")[1]
                    if "Pushing changes" in commit_section:
                        commit_info = commit_section.split("Pushing changes")[0].strip()
                        if "Address PR review feedback" in commit_info:
                            work_summary.append("\n**Commit Created:** ✓ Address PR review feedback")

                if work_summary:
                    comment_body += "\n\n<details>\n<summary>🔧 Agent Work Details (click to expand)</summary>\n\n"
                    comment_body += "\n".join(work_summary)
                    comment_body += "\n\n</details>"

            comment_body += "\n\n*This comment was generated by an AI agent that automatically addresses PR review feedback.*"
        else:
            comment_body = (
                f"{self.agent_tag} I attempted to address the PR review "
                "feedback but encountered some issues. Manual intervention "
                "may be required.\n\n"
                f"The review identified:\n"
                f"- {len(feedback['must_fix'])} critical issues\n"
                f"- {len(feedback['issues'])} inline code comments\n"
                f"- {len(feedback['nice_to_have'])} suggestions\n\n"
            )

            # Add error details if available
            if error_details:
                # Mask any secrets in the error details
                masked_error_details = self.mask_secrets(error_details)
                comment_body += (
                    "**Error Details:**\n"
                    "<details>\n"
                    "<summary>Click to expand error log</summary>\n\n"
                    "```\n"
                    f"{masked_error_details}\n"
                    "```\n\n"
                    "</details>\n\n"
                )

            # Add partial agent output if available (shows what was attempted)
            if self.verbose and agent_output:
                masked_output = self.mask_secrets(agent_output)
                # Extract the most relevant parts
                relevant_sections = []

                if "Running Claude to address review feedback..." in masked_output:
                    relevant_sections.append("**Agent attempted the following:**")
                    # Get the Claude interaction part
                    claude_section = masked_output.split("Running Claude to address review feedback...")[1]
                    if claude_section:
                        relevant_sections.append("```")
                        relevant_sections.append(claude_section[:1000] + ("..." if len(claude_section) > 1000 else ""))
                        relevant_sections.append("```")

                if relevant_sections:
                    comment_body += (
                        "\n**Agent Work Log:**\n" "<details>\n" "<summary>Click to see what the agent attempted</summary>\n\n"
                    )
                    comment_body += "\n".join(relevant_sections)
                    comment_body += "\n\n</details>\n"

            comment_body += (
                "Please review the attempted changes and complete any "
                "remaining fixes manually.\n\n"
                "*This comment was generated by an AI agent.*"
            )

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment_body,
            ]
        )

    def post_pipeline_fix_comment(
        self,
        pr_number: int,
        failures: Dict,
        status: str = "attempting",
        error_details: Optional[str] = None,
        agent_output: Optional[str] = None,
    ) -> None:
        """Post a comment about pipeline fix attempts."""
        if status == "attempting":
            comment_body = f"""{self.agent_tag} 🔧 I've detected failing CI/CD checks and I'm working on fixing them:

**Failed Checks:**
- Lint/Format failures: {len(failures['lint_failures'])}"""
            if failures["lint_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['lint_failures']])})"
            comment_body += f"\n- Test failures: {len(failures['test_failures'])}"
            if failures["test_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['test_failures']])})"
            comment_body += f"\n- Build failures: {len(failures['build_failures'])}"
            if failures["build_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['build_failures']])})"
            comment_body += f"\n- Other failures: {len(failures['other_failures'])}"
            if failures["other_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['other_failures']])})"
            comment_body += """

I'll analyze the failure logs and attempt to fix these issues automatically...

*This comment was generated by an AI agent that monitors and fixes CI/CD pipeline failures.*"""
        elif status == "success":
            comment_body = f"""{self.agent_tag} ✅ I've successfully fixed the pipeline failures:

**Fixed Issues:**
- Resolved {len(failures['lint_failures'])} lint/format issues
- Fixed {len(failures['test_failures'])} test failures
- Corrected {len(failures['build_failures'])} build problems
- Addressed {len(failures['other_failures'])} other issues

All checks should now pass. The PR is ready for review.
"""

            # Add agent work details if verbose mode is enabled
            if self.verbose and agent_output:
                masked_output = self.mask_secrets(agent_output)

                work_summary = []

                # Extract auto-formatting results
                if "Running auto-format" in masked_output:
                    format_section = masked_output.split("Running auto-format")[1]
                    if "Running Claude" in format_section:
                        format_results = format_section.split("Running Claude")[0].strip()
                        if format_results:
                            work_summary.append("**Auto-formatting Results:**")
                            work_summary.append("```")
                            work_summary.append(format_results[:500] + ("..." if len(format_results) > 500 else ""))
                            work_summary.append("```")

                # Extract Claude's analysis
                if "Running Claude to fix pipeline failures..." in masked_output:
                    claude_section = masked_output.split("Running Claude to fix pipeline failures...")[1]
                    if "Running tests to verify" in claude_section:
                        claude_work = claude_section.split("Running tests to verify")[0].strip()
                        if claude_work and len(claude_work) > 100:
                            work_summary.append("\n**Claude's Pipeline Fix Analysis:**")
                            work_summary.append("```")
                            work_summary.append(claude_work[:1500] + ("..." if len(claude_work) > 1500 else ""))
                            work_summary.append("```")

                # Extract verification results
                if "Running tests to verify fixes..." in masked_output:
                    verify_section = masked_output.split("Running tests to verify fixes...")[1]
                    if "Committing fixes..." in verify_section:
                        verify_results = verify_section.split("Committing fixes...")[0].strip()
                        if verify_results:
                            work_summary.append("\n**Verification Results:**")
                            work_summary.append("```")
                            work_summary.append(verify_results[:500] + ("..." if len(verify_results) > 500 else ""))
                            work_summary.append("```")

                if work_summary:
                    comment_body += "\n\n<details>\n<summary>🔧 Pipeline Fix Details (click to expand)</summary>\n\n"
                    comment_body += "\n".join(work_summary)
                    comment_body += "\n\n</details>"

            comment_body += (
                "\n\n*This comment was generated by an AI agent that automatically fixes CI/CD pipeline failures.*" ""
            )
        else:  # failed
            comment_body = f"""{self.agent_tag} ❌ I attempted to fix the pipeline failures but encountered issues:

**Attempted Fixes:**
- Lint/Format failures: {len(failures['lint_failures'])}"""
            if failures["lint_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['lint_failures']])})"
            comment_body += f"\n- Test failures: {len(failures['test_failures'])}"
            if failures["test_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['test_failures']])})"
            comment_body += f"\n- Build failures: {len(failures['build_failures'])}"
            if failures["build_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['build_failures']])})"
            comment_body += f"\n- Other failures: {len(failures['other_failures'])}"
            if failures["other_failures"]:
                comment_body += f" ({', '.join([f['name'] for f in failures['other_failures']])})"
            comment_body += """

Manual intervention may be required to resolve these issues.
"""
            # Add error details if available
            if error_details:
                # Mask any secrets in the error details
                masked_error_details = self.mask_secrets(error_details)
                comment_body += f"""
**Error Details:**
<details>
<summary>Click to expand error log</summary>

```
{masked_error_details}
```

</details>
"""

            # Add partial agent output if available
            if self.verbose and agent_output:
                masked_output = self.mask_secrets(agent_output)
                relevant_sections = []

                if "Running Claude to fix pipeline failures..." in masked_output:
                    relevant_sections.append("**Agent attempted the following fixes:**")
                    claude_section = masked_output.split("Running Claude to fix pipeline failures...")[1]
                    if claude_section:
                        relevant_sections.append("```")
                        relevant_sections.append(claude_section[:1000] + ("..." if len(claude_section) > 1000 else ""))
                        relevant_sections.append("```")

                if relevant_sections:
                    comment_body += """
**Agent Work Log:**
<details>
<summary>Click to see what the agent attempted</summary>

"""
                    comment_body += "\n".join(relevant_sections)
                    comment_body += "\n\n</details>\n"
            comment_body += "\n*This comment was generated by an AI agent that monitors CI/CD pipeline failures.*"

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment_body,
            ]
        )

    def post_security_rejection_comment(self, pr_number: int, reason: Optional[str] = None) -> None:
        """Post a comment explaining why the PR cannot be processed."""
        if reason:
            comment_body = (
                f"{self.agent_tag} Security Notice\n\n"
                f"This request was blocked: {reason}\n\n"
                f"{self.security_manager.reject_message}\n\n"
                "*This is an automated security measure.*"
            )
        else:
            comment_body = (
                f"{self.agent_tag} Security Notice\n\n"
                f"{self.security_manager.reject_message}\n\n"
                "*This is an automated security measure to prevent unauthorized use of AI agents.*"
            )

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment_body,
            ]
        )

        logger.info(f"Posted security rejection comment on PR #{pr_number}")

    def process_pr_reviews(self):
        """Main process to monitor and handle PR reviews."""
        logger.info("=== Starting PR review monitoring ===")
        logger.info(f"Repository: {self.repo}")
        logger.info(f"Auto-fix enabled: {self.auto_fix_enabled}")
        logger.info(f"Required labels: {self.required_labels}")
        logger.info(f"Review bot names: {self.review_bot_names}")
        logger.info(f"Cutoff hours: {self.cutoff_hours}")

        prs = self.get_open_prs()
        logger.info(f"Found {len(prs)} open PRs after filtering by recent activity")

        for pr in prs:
            pr_number = pr["number"]
            branch_name = pr["headRefName"]
            labels = [label.get("name", "") for label in pr.get("labels", [])]
            pr_author = pr.get("author", {}).get("login", "Unknown")

            logger.info(f"\n--- Processing PR #{pr_number} ---")
            logger.info(f"Title: {pr.get('title', 'No title')}")
            logger.info(f"Author: {pr_author}")
            logger.info(f"Branch: {branch_name}")
            logger.info(f"Labels: {labels}")

            # Fetch comments for this PR since pr list doesn't include them
            pr_comments = self.get_pr_general_comments(pr_number)
            pr["comments"] = pr_comments
            if self.verbose:
                logger.debug(f"Fetched {len(pr_comments)} comments for PR #{pr_number}")

            # Check if PR has required labels
            has_required_label = any(label in labels for label in self.required_labels)
            if not has_required_label:
                logger.info(f"[SKIP] PR #{pr_number} does not have required labels {self.required_labels}")
                if self.verbose:
                    logger.debug(f"PR has labels: {labels}, required: {self.required_labels}")
                continue

            # Check for keyword trigger from allowed user
            logger.info(f"[CHECK] Looking for trigger keywords in PR #{pr_number} comments...")
            if self.verbose:
                logger.debug(f"PR has {len(pr.get('comments', []))} comments to check")
                for i, comment in enumerate(pr.get("comments", [])[:5]):
                    author = comment.get("user", {}).get("login", "Unknown")
                    body_preview = comment.get("body", "")[:100]
                    logger.debug(f"  Comment {i}: author={author}, preview={body_preview}...")

            trigger_info = self.security_manager.check_trigger_comment(pr, "pr")

            if not trigger_info:
                logger.info(f"[SKIP] PR #{pr_number} has no valid trigger keyword")
                if self.verbose:
                    logger.debug("No [Action][Agent] pattern found in recent comments")
                continue

            action, agent, trigger_user = trigger_info

            # Check if this agent should handle this trigger
            # For now, we'll handle all triggers, but this is where agent selection would happen
            # In the future: if agent != "Claude": continue

            logger.info(f"Processing PR #{pr_number} triggered by {trigger_user}: [{action}][{agent}]")

            # Enhanced security check with rate limiting and repository validation
            repo = self.repo

            is_allowed, rejection_reason = self.security_manager.perform_full_security_check(
                username=trigger_user,
                action=f"pr_{action.lower()}",
                repository=repo,
                entity_type="pr",
                entity_id=str(pr_number),
            )

            if not is_allowed:
                # Post rejection comment with specific reason
                if not self.has_agent_addressed_review(pr_number):
                    self.post_security_rejection_comment(pr_number, rejection_reason)
                continue

            if self.verbose:
                logger.info(f"Security check passed for user {trigger_user}")

            # Skip if we've already addressed this review
            if self.has_agent_addressed_review(pr_number):
                logger.info(f"[SKIP] Already addressed review for PR #{pr_number}")
                if self.verbose:
                    logger.debug("Found previous agent comment indicating review was addressed")
                continue

            # Check for pipeline failures first
            logger.info(f"[PIPELINE] Checking CI/CD status for PR #{pr_number}...")
            check_status = self.get_pr_check_status(pr_number)
            logger.info(
                f"[PIPELINE] PR #{pr_number}: Total checks: {len(check_status['checks'])}, "
                f"Failing: {len(check_status['failing_checks'])}, "
                f"In progress: {check_status.get('in_progress', False)}"
            )

            # If checks are still in progress, log but don't attempt fixes yet
            if check_status.get("in_progress", False):
                logger.info(f"PR #{pr_number}: Checks still in progress, will check again later")

            if check_status["has_failures"] and not self.has_agent_attempted_pipeline_fix(pr_number):
                logger.info(f"[PIPELINE] PR #{pr_number} has {len(check_status['failing_checks'])} failing CI/CD checks")
                if self.verbose:
                    for check in check_status["failing_checks"][:5]:  # Show first 5
                        logger.debug(f"  - Failed: {check.get('name', 'Unknown check')}")

                failures = self.parse_pipeline_failures(check_status["failing_checks"])
                logger.info(
                    f"[PIPELINE] Failure breakdown: Lint={len(failures['lint_failures'])}, "
                    f"Test={len(failures['test_failures'])}, Build={len(failures['build_failures'])}, "
                    f"Other={len(failures['other_failures'])}"
                )

                # Post comment that we're working on fixing pipeline
                logger.info(f"[ACTION] Posting 'attempting fix' comment on PR #{pr_number}")
                self.post_pipeline_fix_comment(pr_number, failures, "attempting")

                # Attempt to fix the failures
                logger.info(f"[ACTION] Attempting to fix pipeline failures for PR #{pr_number}...")
                success, error_details, agent_output = self.address_pipeline_failures(pr_number, branch_name, failures)

                # Post completion comment
                if success:
                    logger.info(f"[SUCCESS] Pipeline fixes applied successfully for PR #{pr_number}")
                    self.post_pipeline_fix_comment(pr_number, failures, "success", agent_output=agent_output)
                else:
                    logger.error(f"[FAILED] Pipeline fix failed for PR #{pr_number}")
                    if self.verbose and error_details:
                        logger.debug(f"Error details: {error_details[:500]}...")
                    self.post_pipeline_fix_comment(pr_number, failures, "failed", error_details, agent_output)

                # Continue to next PR after handling pipeline failures
                logger.info(f"[DONE] Completed pipeline fix attempt for PR #{pr_number}")
                continue

            # Handle different actions
            if action.lower() in ["approved", "fix", "implement", "review"]:
                logger.info(f"[REVIEW] Processing '{action}' action for PR #{pr_number}")

                # Get reviews and comments
                logger.info(f"[REVIEW] Fetching reviews and comments for PR #{pr_number}...")
                reviews = self.get_pr_reviews(pr_number)
                review_comments = self.get_pr_review_comments(pr_number)
                general_comments = self.get_pr_general_comments(pr_number)

                # Skip if no reviews from bots
                bot_reviews = [r for r in reviews if r.get("author", {}).get("login") in self.review_bot_names]

                # Check for bot comments in general comments too (where Gemini posts)
                bot_general_comments = [
                    c
                    for c in general_comments
                    if c.get("user", {}).get("login") in self.review_bot_names
                    or c.get("user", {}).get("login") == "github-actions"
                ]

                logger.info(
                    f"PR #{pr_number}: Found {len(bot_reviews)} bot reviews, "
                    f"{len(review_comments)} inline comments, "
                    f"{len(bot_general_comments)} bot general comments"
                )

                if not bot_reviews and not review_comments and not bot_general_comments:
                    logger.info(f"[SKIP] No bot reviews found for PR #{pr_number}")
                    if self.verbose:
                        logger.debug(f"Checked for reviews from: {self.review_bot_names}")
                    continue

                # Parse feedback
                logger.info("[REVIEW] Parsing feedback from reviews and comments...")
                feedback = self.parse_review_feedback(bot_reviews, review_comments, general_comments)

                logger.info(
                    f"[REVIEW] Feedback summary: changes_requested={feedback['changes_requested']}, "
                    f"must_fix={len(feedback['must_fix'])}, issues={len(feedback['issues'])}, "
                    f"suggestions={len(feedback['nice_to_have'])}"
                )

                # Only process if changes were requested or issues found
                if feedback["changes_requested"] or feedback["issues"] or feedback["must_fix"]:
                    logger.info(f"[ACTION] Processing review feedback for PR #{pr_number}...")
                    if self.verbose:
                        logger.debug(f"Must fix items: {feedback['must_fix'][:3]}...")  # Show first 3

                    success, error_details, agent_output = self.address_review_feedback(pr_number, branch_name, feedback)

                    if success:
                        logger.info(f"[SUCCESS] Review feedback addressed successfully for PR #{pr_number}")
                    else:
                        logger.error(f"[FAILED] Failed to address review feedback for PR #{pr_number}")
                        if self.verbose and error_details:
                            logger.debug(f"Error details: {error_details[:500]}...")

                    self.post_completion_comment(pr_number, feedback, success, error_details, agent_output)
                else:
                    logger.info(f"[INFO] No changes required for PR #{pr_number} - review passed")

                    # Post comment that no changes needed
                    comment_body = (
                        f"{self.agent_tag} I've reviewed the PR feedback and found "
                        "no changes are required. The PR review passed without any "
                        "critical issues or required fixes.\n\n"
                        "✅ **Review Status:** All checks passed\n"
                        "🎉 **No changes needed**\n\n"
                        "*This comment was generated by an AI agent monitoring PR reviews.*"
                    )

                    logger.info(f"[ACTION] Posting 'no changes needed' comment on PR #{pr_number}")
                    run_gh_command(
                        [
                            "pr",
                            "comment",
                            str(pr_number),
                            "--repo",
                            self.repo,
                            "--body",
                            comment_body,
                        ]
                    )
            elif action.lower() == "close":
                # Close the PR
                logger.info(f"[ACTION] Closing PR #{pr_number} as requested by {trigger_user}")
                run_gh_command(["pr", "close", str(pr_number), "--repo", self.repo])
                self.create_action_comment(
                    pr_number,
                    f"PR closed as requested by {trigger_user} using [{action}][{agent}]",
                )
                logger.info(f"[SUCCESS] PR #{pr_number} closed successfully")
            elif action.lower() == "summarize":
                # Summarize the PR
                logger.info(f"[ACTION] Creating summary for PR #{pr_number}")
                self.create_summary_comment(pr_number, pr)
                logger.info(f"[SUCCESS] Summary posted for PR #{pr_number}")
            else:
                logger.warning(f"[WARNING] Unknown action: {action}")

            logger.info(f"[DONE] Completed processing PR #{pr_number}")

    def create_action_comment(self, pr_number: int, message: str) -> None:
        """Create a comment for an action taken."""
        comment = f"{self.agent_tag} {message}"

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def create_summary_comment(self, pr_number: int, pr: Dict) -> None:
        """Create a summary comment for a PR."""
        title = pr.get("title", "No title")
        body = pr.get("body", "No description")
        labels = [label.get("name", "") for label in pr.get("labels", [])]
        author = pr.get("author", {}).get("login", "Unknown")

        summary = f"""{self.agent_tag} **PR Summary:**

**Title:** {title}

**Author:** @{author}

**Labels:** {', '.join(labels) if labels else 'None'}

**Description Summary:** {body[:200]}{'...' if len(body) > 200 else ''}

**Branch:** `{pr.get('headRefName', 'Unknown')}`

**Reviews:** {len(pr.get('reviews', []))} review(s), {len(pr.get('comments', []))} comment(s)
"""

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                summary,
            ]
        )


def main():
    """Main entry point."""
    logger.info("=== PR Review Monitor Starting ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")

    monitor = PRReviewMonitor()

    if "--continuous" in sys.argv:
        # Run continuously
        while True:
            try:
                monitor.process_pr_reviews()
                time.sleep(300)  # Check every 5 minutes
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(60)  # Wait a minute before retrying
    else:
        # Run once
        monitor.process_pr_reviews()


if __name__ == "__main__":
    main()
