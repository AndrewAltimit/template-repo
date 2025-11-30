"""
AI Agent Visual Analysis Integration for Dashboard Testing.
Analyzes screenshots captured during Selenium tests for visual issues.
"""

import base64
from datetime import datetime
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List


class AIVisualAnalyzer:
    """Integrates with AI agents to analyze dashboard screenshots."""

    def __init__(self):
        """Initialize AI visual analyzer."""
        self.results_dir = Path(__file__).parent / "ai_analysis_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def analyze_with_claude(self, screenshot_path: Path, context: str = "") -> Dict[str, Any]:
        """Analyze screenshot using Claude AI.

        Args:
            screenshot_path: Path to screenshot file
            context: Additional context for analysis

        Returns:
            Analysis results from Claude
        """
        prompt = f"""
        Analyze this dashboard screenshot for:
        1. Visual layout issues (misaligned elements, overlapping content)
        2. Color contrast and readability problems
        3. Missing or broken UI components
        4. Chart rendering issues
        5. Responsive design problems
        6. General UX/UI improvements

        Context: {context}

        Please provide a structured analysis with:
        - Issues found (if any)
        - Severity (critical/high/medium/low)
        - Suggested fixes
        - Overall quality score (1-10)
        """

        # Create temporary script for Claude CLI
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Call Claude CLI with image
            result = subprocess.run(
                ["claude", "chat", "--image", str(screenshot_path), "--file", prompt_file],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode == 0:
                return {"status": "success", "analysis": result.stdout, "timestamp": datetime.now().isoformat()}
            else:
                return {"status": "error", "error": result.stderr, "timestamp": datetime.now().isoformat()}

        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}
        finally:
            # Clean up temp file
            Path(prompt_file).unlink(missing_ok=True)

    def analyze_with_gemini(self, screenshot_path: Path, context: str = "") -> Dict[str, Any]:
        """Analyze screenshot using Gemini AI.

        Args:
            screenshot_path: Path to screenshot file
            context: Additional context for analysis

        Returns:
            Analysis results from Gemini
        """
        # Read image and encode to base64
        with open(screenshot_path, "rb") as f:
            _ = base64.b64encode(f.read()).decode("utf-8")  # For future AI

        prompt = f"""
        Analyze this dashboard screenshot for visual quality:

        Context: {context}

        Check for:
        - Layout consistency
        - Visual hierarchy
        - Color scheme appropriateness
        - Information density
        - Accessibility concerns
        - Mobile responsiveness indicators

        Provide actionable feedback.
        """

        try:
            # Call Gemini CLI
            result = subprocess.run(
                ["gemini", "analyze", "--image", str(screenshot_path), "--prompt", prompt],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode == 0:
                return {"status": "success", "analysis": result.stdout, "timestamp": datetime.now().isoformat()}
            else:
                return {"status": "error", "error": result.stderr, "timestamp": datetime.now().isoformat()}

        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    def compare_screenshots(self, before_path: Path, after_path: Path) -> Dict[str, Any]:
        """Use AI to compare before/after screenshots.

        Args:
            before_path: Path to before screenshot
            after_path: Path to after screenshot

        Returns:
            Comparison analysis
        """
        _ = """
        Compare these two dashboard screenshots:
        1. What changed between them?
        2. Are the changes improvements or regressions?
        3. Any visual issues introduced?
        4. Rate the change impact (1-10 scale)
        """

        # Try Claude first, fallback to Gemini
        result = self.analyze_with_claude(after_path, f"Comparing with baseline: {before_path}")

        if result.get("status") != "success":
            result = self.analyze_with_gemini(after_path, f"Comparing with baseline: {before_path}")

        return result

    def batch_analyze(self, screenshots_dir: Path) -> List[Dict[str, Any]]:
        """Analyze all screenshots in a directory.

        Args:
            screenshots_dir: Directory containing screenshots

        Returns:
            List of analysis results
        """
        results = []

        for screenshot_path in screenshots_dir.glob("*.png"):
            print(f"Analyzing {screenshot_path.name}...")

            # Determine context from filename
            context = self._get_context_from_filename(screenshot_path.name)

            # Analyze with AI
            analysis = self.analyze_with_claude(screenshot_path, context)

            # If Claude fails, try Gemini
            if analysis.get("status") != "success":
                analysis = self.analyze_with_gemini(screenshot_path, context)

            # Add metadata
            analysis["screenshot"] = str(screenshot_path)
            analysis["filename"] = screenshot_path.name

            results.append(analysis)

            # Save individual result
            self._save_analysis_result(screenshot_path.name, analysis)

        # Save batch results
        batch_file = self.results_dir / f"batch_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(batch_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

    def check_accessibility(self, screenshot_path: Path) -> Dict[str, Any]:
        """Specialized accessibility analysis.

        Args:
            screenshot_path: Path to screenshot

        Returns:
            Accessibility analysis results
        """
        prompt = """
        Analyze this dashboard for accessibility issues:
        1. Color contrast (WCAG AA/AAA compliance)
        2. Text readability
        3. Visual hierarchy for screen readers
        4. Interactive element sizing (minimum 44x44px)
        5. Focus indicators visibility
        6. Error message clarity

        Provide specific WCAG guideline references where applicable.
        """

        result = self.analyze_with_claude(screenshot_path, prompt)
        result["check_type"] = "accessibility"
        return result

    def validate_responsive_design(self, screenshots: Dict[str, Path]) -> Dict[str, Any]:
        """Validate responsive design across different viewports.

        Args:
            screenshots: Dictionary of viewport size to screenshot path

        Returns:
            Responsive design validation results
        """
        results = {}

        for viewport, screenshot_path in screenshots.items():
            context = f"Viewport: {viewport}. Check if layout adapts properly for this screen size."
            analysis = self.analyze_with_claude(screenshot_path, context)

            results[viewport] = {"analysis": analysis, "viewport": viewport, "screenshot": str(screenshot_path)}

        return results

    def generate_report(self, test_run_id: str) -> Path:
        """Generate comprehensive visual test report.

        Args:
            test_run_id: Unique identifier for test run

        Returns:
            Path to generated report
        """
        # Collect all analysis results for this test run
        analyses = []
        for result_file in self.results_dir.glob(f"*{test_run_id}*.json"):
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle both single dict and list of dicts
                if isinstance(data, list):
                    analyses.extend(data)
                else:
                    analyses.append(data)

        # Generate markdown report
        report_content = self._generate_markdown_report(analyses)

        # Save report
        report_path = self.results_dir / f"visual_test_report_{test_run_id}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        return Path(report_path)

    def _get_context_from_filename(self, filename: str) -> str:
        """Extract context from screenshot filename."""
        contexts = {
            "login": "Login page UI",
            "dashboard": "Main dashboard view",
            "chart": "Data visualization chart",
            "export": "Export functionality UI",
            "error": "Error state display",
            "responsive": "Responsive design test",
            "model": "Model selection interface",
            "navigation": "Navigation menu",
        }

        for key, context in contexts.items():
            if key in filename.lower():
                return context

        return "Dashboard component"

    def _save_analysis_result(self, screenshot_name: str, analysis: Dict[str, Any]):
        """Save individual analysis result."""
        result_file = self.results_dir / f"{screenshot_name}_analysis.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2)

    def _generate_markdown_report(self, analyses: List[Dict[str, Any]]) -> str:
        """Generate markdown report from analyses."""
        report = "# Visual Test Analysis Report\n\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Summary
        report += "## Summary\n\n"
        total = len(analyses)
        successful = sum(1 for a in analyses if a.get("status") == "success")
        report += f"- Total screenshots analyzed: {total}\n"
        report += f"- Successful analyses: {successful}\n"
        report += f"- Failed analyses: {total - successful}\n\n"

        # Detailed results
        report += "## Detailed Analysis\n\n"

        for analysis in analyses:
            screenshot = analysis.get("filename", "Unknown")
            report += f"### {screenshot}\n\n"

            if analysis.get("status") == "success":
                report += f"**Analysis:**\n{analysis.get('analysis', 'No analysis available')}\n\n"
            else:
                report += f"**Error:**\n{analysis.get('error', 'Unknown error')}\n\n"

        return report


class VisualTestRunner:
    """Runner for visual regression tests with AI analysis."""

    def __init__(self):
        """Initialize visual test runner."""
        self.analyzer = AIVisualAnalyzer()
        self.screenshots_dir = Path(__file__).parent / "screenshots"

    def run_visual_tests(self, test_suite: str = "all") -> Dict[str, Any]:
        """Run visual tests and analyze results.

        Args:
            test_suite: Test suite to run

        Returns:
            Test results with AI analysis
        """
        # Run Selenium tests
        print("Running Selenium E2E tests...")
        test_result = subprocess.run(
            ["python", "-m", "pytest", "test_selenium_e2e.py", "-v"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            check=False,
        )

        # Analyze captured screenshots
        print("Analyzing screenshots with AI...")
        analyses = self.analyzer.batch_analyze(self.screenshots_dir)

        # Generate report
        test_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.analyzer.generate_report(test_run_id)

        return {
            "test_result": {"passed": test_result.returncode == 0, "output": test_result.stdout, "errors": test_result.stderr},
            "visual_analysis": analyses,
            "report": str(report_path),
            "timestamp": datetime.now().isoformat(),
        }

    def run_accessibility_tests(self) -> Dict[str, Any]:
        """Run specialized accessibility tests."""
        results = []

        for screenshot in self.screenshots_dir.glob("*.png"):
            print(f"Running accessibility check on {screenshot.name}...")
            result = self.analyzer.check_accessibility(screenshot)
            results.append(result)

        return {"accessibility_results": results, "timestamp": datetime.now().isoformat()}

    def run_responsive_tests(self) -> Dict[str, Any]:
        """Run responsive design validation tests."""
        # Group screenshots by viewport
        viewports = {}
        for screenshot in self.screenshots_dir.glob("responsive_*.png"):
            # Extract viewport from filename
            parts = screenshot.stem.split("_")
            if len(parts) >= 2:
                viewport = parts[1]  # e.g., "1920x1080"
                viewports[viewport] = screenshot

        if viewports:
            result: Dict[str, Any] = self.analyzer.validate_responsive_design(viewports)
            return result
        return {"error": "No responsive screenshots found"}


if __name__ == "__main__":
    # Example usage
    runner = VisualTestRunner()

    print("Starting visual regression testing with AI analysis...")

    # Run full test suite
    results = runner.run_visual_tests()

    print(f"\nTest Results: {'PASSED' if results['test_result']['passed'] else 'FAILED'}")
    print(f"Report generated: {results['report']}")

    # Run accessibility tests
    print("\nRunning accessibility tests...")
    accessibility_results = runner.run_accessibility_tests()
    print(f"Accessibility tests completed: {len(accessibility_results['accessibility_results'])} screenshots analyzed")

    # Run responsive tests
    print("\nRunning responsive design tests...")
    responsive_results = runner.run_responsive_tests()
    print("Responsive tests completed")
