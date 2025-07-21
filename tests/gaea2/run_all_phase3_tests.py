#!/usr/bin/env python3
"""
Comprehensive test runner for Phase 3 of Gaea2 MCP testing.
This implements the autonomous testing approach from the AI Agent Training Guide.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest


class Phase3TestRunner:
    """Runs all Phase 3 tests autonomously and generates comprehensive reports."""

    def __init__(self, mcp_url: str = "http://192.168.0.152:8007"):
        self.mcp_url = mcp_url
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "mcp_url": mcp_url,
            "test_suites": {},
            "summary": {},
        }

    def run_pytest_suite(self, test_file: str, suite_name: str) -> Dict[str, Any]:
        """Run a pytest test suite and capture results."""
        print(f"\n🧪 Running {suite_name}...")

        # Run pytest with JSON report
        result = pytest.main(
            [
                test_file,
                "-v",
                "--json-report",
                f"--json-report-file=temp_{suite_name}.json",
                "--tb=short",
            ]
        )

        # Read the JSON report
        report_file = Path(f"temp_{suite_name}.json")
        if report_file.exists():
            with open(report_file) as f:
                report_data = json.load(f)
            report_file.unlink()  # Clean up

            return {
                "exit_code": result,
                "total": report_data["summary"]["total"],
                "passed": report_data["summary"].get("passed", 0),
                "failed": report_data["summary"].get("failed", 0),
                "skipped": report_data["summary"].get("skipped", 0),
                "duration": report_data["duration"],
                "tests": report_data["tests"],
            }
        else:
            return {"exit_code": result, "error": "Failed to generate test report"}

    async def run_connectivity_test(self) -> Dict[str, Any]:
        """Run the connectivity test script."""
        print("\n🌐 Running connectivity tests...")

        # Import and run the connectivity tester
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from test_gaea_mcp_server import Gaea2MCPTester

        tester = Gaea2MCPTester(self.mcp_url)
        await tester.run_all_tests()

        return {
            "results": tester.results,
            "success": all(r[1].get("success") for r in tester.results),
        }

    def analyze_test_results(self) -> Dict[str, Any]:
        """Analyze all test results and identify patterns."""
        analysis = {
            "total_suites": len(self.results["test_suites"]),
            "total_tests": 0,
            "total_passed": 0,
            "total_failed": 0,
            "failed_tests": [],
            "performance_metrics": {},
            "common_failures": {},
            "recommendations": [],
        }

        # Aggregate results
        for suite_name, suite_data in self.results["test_suites"].items():
            if "error" not in suite_data:
                analysis["total_tests"] += suite_data.get("total", 0)
                analysis["total_passed"] += suite_data.get("passed", 0)
                analysis["total_failed"] += suite_data.get("failed", 0)

                # Collect failed tests
                for test in suite_data.get("tests", []):
                    if test["outcome"] == "failed":
                        analysis["failed_tests"].append(
                            {
                                "suite": suite_name,
                                "test": test["nodeid"],
                                "error": test.get("call", {}).get("longrepr", "Unknown error"),
                            }
                        )

                # Performance metrics
                if "duration" in suite_data:
                    analysis["performance_metrics"][suite_name] = suite_data["duration"]

        # Identify common failure patterns
        failure_keywords = {}
        for failed_test in analysis["failed_tests"]:
            error_str = str(failed_test["error"]).lower()
            for keyword in [
                "connection",
                "timeout",
                "validation",
                "template",
                "node",
                "property",
            ]:
                if keyword in error_str:
                    failure_keywords[keyword] = failure_keywords.get(keyword, 0) + 1

        analysis["common_failures"] = failure_keywords

        # Generate recommendations
        if analysis["total_failed"] == 0:
            analysis["recommendations"].append("✅ All tests passed! The Gaea2 MCP is functioning correctly.")
        else:
            if "connection" in failure_keywords:
                analysis["recommendations"].append("🔌 Check server connectivity and network configuration")
            if "timeout" in failure_keywords:
                analysis["recommendations"].append("⏱️  Consider increasing timeout values or optimizing server performance")
            if "validation" in failure_keywords:
                analysis["recommendations"].append("🔍 Review validation logic and ensure it matches Gaea2 requirements")
            if "template" in failure_keywords:
                analysis["recommendations"].append("📋 Verify all templates are correctly implemented")

        return analysis

    def generate_knowledge_base_update(self) -> Dict[str, Any]:
        """Generate updates for the AI agent knowledge base based on test results."""
        knowledge_update = {
            "timestamp": datetime.now().isoformat(),
            "successful_patterns": [],
            "failure_patterns": [],
            "edge_cases_discovered": [],
            "performance_benchmarks": {},
        }

        # Extract successful patterns
        for suite_name, suite_data in self.results["test_suites"].items():
            if "tests" in suite_data:
                for test in suite_data["tests"]:
                    if test["outcome"] == "passed" and "workflow" in test["nodeid"]:
                        knowledge_update["successful_patterns"].append(
                            {
                                "test": test["nodeid"],
                                "duration": test.get("duration", 0),
                            }
                        )

        # Extract failure patterns for learning
        analysis = self.analyze_test_results()
        for failed_test in analysis["failed_tests"]:
            knowledge_update["failure_patterns"].append(
                {
                    "test": failed_test["test"],
                    "error_type": self._classify_error(failed_test["error"]),
                }
            )

        # Performance benchmarks
        knowledge_update["performance_benchmarks"] = analysis["performance_metrics"]

        return knowledge_update

    def _classify_error(self, error: str) -> str:
        """Classify error type for knowledge base."""
        error_lower = str(error).lower()
        if "connection" in error_lower or "network" in error_lower:
            return "connectivity"
        elif "validation" in error_lower:
            return "validation"
        elif "timeout" in error_lower:
            return "timeout"
        elif "not found" in error_lower or "missing" in error_lower:
            return "missing_resource"
        else:
            return "unknown"

    async def run_all_tests(self):
        """Run all Phase 3 tests autonomously."""
        print("🚀 Starting Phase 3 Autonomous Testing for Gaea2 MCP")
        print(f"   Server URL: {self.mcp_url}")
        print(f"   Timestamp: {datetime.now()}")
        print("=" * 60)

        # 1. Connectivity tests
        connectivity_results = await self.run_connectivity_test()
        self.results["test_suites"]["connectivity"] = connectivity_results

        if not connectivity_results["success"]:
            print("\n❌ Connectivity tests failed. Aborting further tests.")
            self.generate_report()
            return

        # 2. Framework tests (Phase 3 comprehensive suite)
        framework_results = self.run_pytest_suite("tests/gaea2/test_framework_phase3.py", "framework_phase3")
        self.results["test_suites"]["framework_phase3"] = framework_results

        # 3. Operations tests (successful operations)
        operations_results = self.run_pytest_suite("tests/gaea2/test_gaea_operations.py", "operations")
        self.results["test_suites"]["operations"] = operations_results

        # 4. Failure tests (expected failures and error handling)
        failure_results = self.run_pytest_suite("tests/gaea2/test_gaea_failures.py", "failures")
        self.results["test_suites"]["failures"] = failure_results

        # 5. Regression tests
        regression_results = self.run_pytest_suite("tests/gaea2/test_gaea_regression.py", "regression")
        self.results["test_suites"]["regression"] = regression_results

        # Analyze and generate report
        self.results["analysis"] = self.analyze_test_results()
        self.results["knowledge_update"] = self.generate_knowledge_base_update()

        self.generate_report()

    def generate_report(self):
        """Generate comprehensive test report."""
        # Console summary
        print("\n" + "=" * 60)
        print("📊 PHASE 3 TEST SUMMARY")
        print("=" * 60)

        analysis = self.results.get("analysis", self.analyze_test_results())

        print(f"\nTotal Test Suites: {analysis['total_suites']}")
        print(f"Total Tests: {analysis['total_tests']}")
        print(f"Passed: {analysis['total_passed']} ✅")
        print(f"Failed: {analysis['total_failed']} ❌")

        if analysis["total_tests"] > 0:
            pass_rate = (analysis["total_passed"] / analysis["total_tests"]) * 100
            print(f"Pass Rate: {pass_rate:.1f}%")

        if analysis["failed_tests"]:
            print("\n❌ Failed Tests:")
            for failed in analysis["failed_tests"][:5]:  # Show first 5
                print(f"  - {failed['suite']}: {failed['test']}")
            if len(analysis["failed_tests"]) > 5:
                print(f"  ... and {len(analysis['failed_tests']) - 5} more")

        if analysis["common_failures"]:
            print("\n🔍 Common Failure Patterns:")
            for pattern, count in sorted(analysis["common_failures"].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {pattern}: {count} occurrences")

        print("\n💡 Recommendations:")
        for rec in analysis["recommendations"]:
            print(f"  {rec}")

        # Save detailed report
        report_file = f"phase3_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\n💾 Detailed report saved to: {report_file}")

        # Save knowledge base update
        kb_file = f"knowledge_base_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(kb_file, "w") as f:
            json.dump(self.results.get("knowledge_update", {}), f, indent=2)

        print(f"🧠 Knowledge base update saved to: {kb_file}")

        # Exit code based on results
        if analysis["total_failed"] == 0:
            print("\n🎉 All Phase 3 tests passed! The AI agent has successfully validated the Gaea2 MCP.")
            sys.exit(0)
        else:
            print(f"\n⚠️  {analysis['total_failed']} tests failed. Review the detailed report for more information.")
            sys.exit(1)


async def main():
    """Main entry point."""
    # Check if custom server URL is provided
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.0.152:8007"

    runner = Phase3TestRunner(server_url)
    await runner.run_all_tests()


if __name__ == "__main__":
    # Ensure we're in the right directory
    import os

    os.chdir(Path(__file__).parent.parent.parent)

    asyncio.run(main())
