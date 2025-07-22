#!/usr/bin/env python3
"""
Test all Gaea2 templates using the validation system
This script generates variations of each template and validates them
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict

import requests


class Gaea2TemplateValidator:
    """Test all Gaea2 templates systematically"""

    def __init__(self, server_url: str = "http://192.168.0.152:8007"):
        self.server_url = server_url
        self.results = {}

    async def test_all_templates(self, variations: int = 3) -> Dict[str, Any]:
        """Test all available templates"""

        # List of all available templates
        templates = [
            "basic_terrain",
            "detailed_mountain",
            "volcanic_terrain",
            "desert_canyon",
            "modular_portal_terrain",
            "mountain_range",
            "volcanic_island",
            "canyon_system",
            "coastal_cliffs",
            "arctic_terrain",
            "river_valley",
        ]

        print(f"Testing {len(templates)} templates with {variations} variations each...")
        print(f"Server: {self.server_url}")
        print("=" * 60)

        # Test each template
        for template in templates:
            print(f"\nTesting template: {template}")
            print("-" * 40)

            try:
                # Call the test_gaea2_template MCP tool
                payload = {
                    "tool": "test_gaea2_template",
                    "parameters": {
                        "template_name": template,
                        "variations": variations,
                        "server_url": self.server_url,
                    },
                }

                response = requests.post(
                    f"{self.server_url}/mcp/execute",
                    json=payload,
                    timeout=300,  # 5 minute timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    self.results[template] = result

                    # Print summary
                    if result.get("success"):
                        total = result.get("total_files", 0)
                        successful = result.get("successful", 0)
                        failed = result.get("failed", 0)

                        print(f"✓ Tested {total} variations")
                        print(f"  - Successful: {successful}")
                        print(f"  - Failed: {failed}")

                        if failed > 0 and result.get("common_errors"):
                            print("  - Common errors:")
                            for error_type, count in result["common_errors"][:3]:
                                print(f"    • {error_type}: {count} occurrences")
                    else:
                        print(f"✗ Test failed: {result.get('error', 'Unknown error')}")
                else:
                    print(f"✗ HTTP error {response.status_code}")
                    self.results[template] = {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                    }

            except Exception as e:
                print(f"✗ Exception: {str(e)}")
                self.results[template] = {"success": False, "error": str(e)}

        return self.generate_summary()

    def generate_summary(self) -> Dict[str, Any]:
        """Generate comprehensive summary of test results"""

        print("\n" + "=" * 60)
        print("SUMMARY REPORT")
        print("=" * 60)

        # Overall statistics
        total_templates = len(self.results)
        working_templates = []
        failing_templates = []
        partial_templates = []

        for template, result in self.results.items():
            if not result.get("success"):
                failing_templates.append(template)
            elif result.get("successful", 0) == result.get("total_files", 0):
                working_templates.append(template)
            else:
                partial_templates.append(template)

        print(f"\nTotal templates tested: {total_templates}")
        print(f"✓ Fully working: {len(working_templates)} " f"({len(working_templates)/total_templates*100:.0f}%)")
        print(f"⚠ Partially working: {len(partial_templates)} " f"({len(partial_templates)/total_templates*100:.0f}%)")
        print(f"✗ Failed to test: {len(failing_templates)} " f"({len(failing_templates)/total_templates*100:.0f}%)")

        # List templates by category
        if working_templates:
            print("\n✓ FULLY WORKING TEMPLATES:")
            for t in working_templates:
                print(f"  - {t}")

        if partial_templates:
            print("\n⚠ PARTIALLY WORKING TEMPLATES:")
            for t in partial_templates:
                result = self.results[t]
                success_rate = result.get("successful", 0) / result.get("total_files", 1) * 100
                print(f"  - {t} ({success_rate:.0f}% success rate)")

        if failing_templates:
            print("\n✗ FAILED TEMPLATES:")
            for t in failing_templates:
                error = self.results[t].get("error", "Unknown error")
                print(f"  - {t}: {error}")

        # Common error patterns across all templates
        all_errors = {}
        for template, result in self.results.items():
            if result.get("error_types"):
                for error_type, count in result["error_types"].items():
                    all_errors[error_type] = all_errors.get(error_type, 0) + count

        if all_errors:
            print("\nCOMMON ERROR PATTERNS:")
            sorted_errors = sorted(all_errors.items(), key=lambda x: x[1], reverse=True)
            for error_type, count in sorted_errors[:5]:
                print(f"  - {error_type}: {count} occurrences")

        # Save detailed results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"gaea2_template_validation_report_{timestamp}.json"

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "server_url": self.server_url,
            "summary": {
                "total_templates": total_templates,
                "working_templates": working_templates,
                "partial_templates": partial_templates,
                "failing_templates": failing_templates,
                "common_errors": dict(all_errors) if all_errors else {},
            },
            "detailed_results": self.results,
        }

        with open(report_file, "w") as f:
            json.dumps(report_data, f, indent=2)

        print(f"\nDetailed report saved to: {report_file}")

        return report_data


async def main():
    """Main entry point"""

    # Parse command line arguments
    server_url = "http://192.168.0.152:8007"  # Default remote server
    variations = 3

    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    if len(sys.argv) > 2:
        variations = int(sys.argv[2])

    print("Gaea2 Template Validation Test")
    print("=" * 60)

    # Check if server is accessible
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"✓ Server is healthy: {health.get('server', 'Unknown')}")
            if health.get("gaea_configured"):
                print(f"✓ Gaea2 configured: {health.get('gaea_path', 'Yes')}")
            else:
                print("⚠ Warning: Gaea2 not configured on server")
                print("  File validation will not work without Gaea2 executable")
                return
        else:
            print(f"✗ Server health check failed: HTTP {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Cannot connect to server: {e}")
        return

    # Run validation tests
    validator = Gaea2TemplateValidator(server_url)
    await validator.test_all_templates(variations)


if __name__ == "__main__":
    asyncio.run(main())
