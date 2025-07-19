#!/usr/bin/env python3
"""
Comprehensive Gaea2 MCP Testing Script

Tests all aspects of the Gaea2 MCP server:
1. Template creation from various sources
2. Validation and error recovery
3. Performance optimization
4. Edge cases and error handling
5. Knowledge validation
"""

import json
import time
from datetime import datetime
from typing import Any, Dict

import requests

from gaea2_test_templates import Gaea2TestTemplates


class Gaea2ComprehensiveTester:
    """Comprehensive testing suite for Gaea2 MCP"""

    def __init__(self, server_url: str = "http://192.168.0.152:8007"):
        self.server_url = server_url
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 0},
        }

    def call_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool and return the result"""
        try:
            response = requests.post(
                f"{self.server_url}/mcp/execute",
                json={"tool": tool_name, "parameters": parameters},
                timeout=30,
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_test_result(self, test_name: str, result: Dict[str, Any], expected_success: bool = True):
        """Add a test result to the report"""
        success = result.get("success", False)
        passed = success == expected_success

        test_result = {
            "name": test_name,
            "passed": passed,
            "expected_success": expected_success,
            "actual_success": success,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }

        self.results["tests"].append(test_result)
        self.results["summary"]["total"] += 1

        if passed:
            self.results["summary"]["passed"] += 1
            print(f"✓ {test_name}")
        else:
            self.results["summary"]["failed"] += 1
            print(f"✗ {test_name}")
            if "error" in result:
                print(f"  Error: {result['error']}")

    def test_health_check(self):
        """Test server health"""
        print("\n=== Testing Server Health ===")
        try:
            response = requests.get(f"{self.server_url}/health")
            result = response.json()
            self.add_test_result("Server Health Check", {"success": result.get("status") == "healthy"})
        except Exception as e:
            self.add_test_result("Server Health Check", {"success": False, "error": str(e)})

    def test_template_creation(self):
        """Test creating projects from all templates"""
        print("\n=== Testing Template Creation ===")

        templates = Gaea2TestTemplates.get_all_templates()

        for template in templates:
            # Test direct workflow creation
            result = self.call_mcp_tool(
                "create_gaea2_project",
                {
                    "project_name": f"Test_{template['name']}",
                    "workflow": {
                        "nodes": template["nodes"],
                        "connections": template["connections"],
                    },
                    "auto_validate": True,
                },
            )
            self.add_test_result(f"Create {template['name']} (direct)", result)

            # Test validation only
            val_result = self.call_mcp_tool(
                "validate_and_fix_workflow",
                {
                    "workflow": {
                        "nodes": template["nodes"],
                        "connections": template["connections"],
                    },
                    "fix_errors": False,
                },
            )
            self.add_test_result(f"Validate {template['name']}", val_result)

    def test_builtin_templates(self):
        """Test built-in template system"""
        print("\n=== Testing Built-in Templates ===")

        template_names = [
            "basic_terrain",
            "detailed_mountain",
            "volcanic_terrain",
            "desert_canyon",
            "invalid_template",  # Test error handling
        ]

        for template_name in template_names:
            result = self.call_mcp_tool(
                "create_gaea2_from_template",
                {
                    "template_name": template_name,
                    "project_name": f"BuiltIn_{template_name}",
                },
            )
            # Expect failure for invalid template
            expected = template_name != "invalid_template"
            self.add_test_result(f"Built-in template: {template_name}", result, expected_success=expected)

    def test_error_recovery(self):
        """Test error recovery and validation"""
        print("\n=== Testing Error Recovery ===")

        # Test cases with intentional errors
        error_cases = [
            {
                "name": "Missing Export Node",
                "workflow": {
                    "nodes": [{"id": "m1", "type": "Mountain", "properties": {}}],
                    "connections": [],
                },
            },
            {
                "name": "Invalid Property Values",
                "workflow": {
                    "nodes": [
                        {
                            "id": "m1",
                            "type": "Mountain",
                            "properties": {"Height": 5.0},
                        },  # Out of range
                        {"id": "e1", "type": "Export", "properties": {}},
                    ],
                    "connections": [{"from": "m1", "to": "e1"}],
                },
            },
            {
                "name": "Duplicate Connections",
                "workflow": {
                    "nodes": [
                        {"id": "m1", "type": "Mountain"},
                        {"id": "e1", "type": "Erosion2"},
                        {"id": "ex1", "type": "Export"},
                    ],
                    "connections": [
                        {"from": "m1", "to": "e1"},
                        {"from": "m1", "to": "e1"},  # Duplicate
                        {"from": "e1", "to": "ex1"},
                    ],
                },
            },
            {
                "name": "Orphaned Nodes",
                "workflow": {
                    "nodes": [
                        {"id": "m1", "type": "Mountain"},
                        {"id": "orphan", "type": "Erosion2"},  # Not connected
                        {"id": "ex1", "type": "Export"},
                    ],
                    "connections": [{"from": "m1", "to": "ex1"}],
                },
            },
        ]

        for case in error_cases:
            # Test with auto-fix enabled
            result = self.call_mcp_tool(
                "validate_and_fix_workflow",
                {
                    "workflow": case["workflow"],
                    "fix_errors": True,
                    "add_missing_nodes": True,
                },
            )
            self.add_test_result(f"Fix errors: {case['name']}", result)

    def test_optimization(self):
        """Test workflow optimization"""
        print("\n=== Testing Optimization ===")

        # Create a workflow that can be optimized
        workflow = {
            "nodes": [
                {"id": "m1", "type": "Mountain", "properties": {"Height": 0.8}},
                {
                    "id": "e1",
                    "type": "Erosion2",
                    "properties": {
                        "Strength": 0.9,
                        "Iterations": 50,
                        "Detail": 0.9,
                    },  # High value  # High value
                },
                {
                    "id": "t1",
                    "type": "Terrace",
                    "properties": {"Levels": 64},
                },  # High value
                {"id": "s1", "type": "SatMap", "properties": {}},
                {"id": "ex1", "type": "Export", "properties": {}},
            ],
            "connections": [
                {"from": "m1", "to": "e1"},
                {"from": "e1", "to": "t1"},
                {"from": "t1", "to": "s1"},
                {"from": "s1", "to": "ex1"},
            ],
        }

        # Test different optimization modes
        for mode in ["performance", "quality", "balanced"]:
            result = self.call_mcp_tool(
                "optimize_gaea2_properties",
                {"workflow": workflow, "optimization_mode": mode},
            )
            self.add_test_result(f"Optimize for {mode}", result)

    def test_node_suggestions(self):
        """Test intelligent node suggestions"""
        print("\n=== Testing Node Suggestions ===")

        test_cases = [
            {
                "name": "After Mountain",
                "nodes": ["Mountain"],
                "context": "realistic terrain",
            },
            {
                "name": "After Erosion",
                "nodes": ["Mountain", "Erosion2"],
                "context": "detailed terrain",
            },
            {
                "name": "Complex Chain",
                "nodes": ["Mountain", "Erosion2", "Terrace", "SatMap"],
                "context": "final output",
            },
            {"name": "Empty Workflow", "nodes": [], "context": "starting new terrain"},
        ]

        for case in test_cases:
            result = self.call_mcp_tool(
                "suggest_gaea2_nodes",
                {
                    "current_nodes": case["nodes"],
                    "context": case["context"],
                    "limit": 5,
                },
            )
            self.add_test_result(f"Suggest nodes: {case['name']}", result)

    def test_workflow_analysis(self):
        """Test workflow pattern analysis"""
        print("\n=== Testing Workflow Analysis ===")

        # Test with different workflow complexities
        workflows = [
            {
                "name": "Simple Linear",
                "workflow": {
                    "nodes": [
                        {"id": "1", "type": "Mountain"},
                        {"id": "2", "type": "Erosion2"},
                        {"id": "3", "type": "Export"},
                    ],
                    "connections": [{"from": "1", "to": "2"}, {"from": "2", "to": "3"}],
                },
            },
            {
                "name": "Branching",
                "workflow": {
                    "nodes": [
                        {"id": "1", "type": "Mountain"},
                        {"id": "2", "type": "Erosion2"},
                        {"id": "3", "type": "Terrace"},
                        {"id": "4", "type": "Combine"},
                        {"id": "5", "type": "Export"},
                    ],
                    "connections": [
                        {"from": "1", "to": "2"},
                        {"from": "1", "to": "3"},
                        {"from": "2", "to": "4"},
                        {"from": "3", "to": "4"},
                        {"from": "4", "to": "5"},
                    ],
                },
            },
        ]

        for case in workflows:
            result = self.call_mcp_tool(
                "analyze_workflow_patterns",
                {
                    "workflow_or_directory": case["workflow"],
                    "include_suggestions": True,
                },
            )
            self.add_test_result(f"Analyze pattern: {case['name']}", result)

    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        print("\n=== Testing Edge Cases ===")

        # Test empty workflow
        result = self.call_mcp_tool(
            "create_gaea2_project",
            {
                "project_name": "EmptyProject",
                "workflow": {"nodes": [], "connections": []},
            },
        )
        self.add_test_result("Empty workflow", result, expected_success=False)

        # Test very long node chain
        nodes = []
        connections = []
        for i in range(50):
            nodes.append(
                {
                    "id": f"node{i}",
                    "type": "Mountain" if i % 2 == 0 else "Erosion2",
                    "properties": {},
                }
            )
            if i > 0:
                connections.append({"from": f"node{i-1}", "to": f"node{i}"})

        result = self.call_mcp_tool(
            "validate_and_fix_workflow",
            {
                "workflow": {"nodes": nodes, "connections": connections},
                "fix_errors": True,
            },
        )
        self.add_test_result("Very long node chain", result)

        # Test circular dependency
        circular_workflow = {
            "nodes": [
                {"id": "a", "type": "Mountain"},
                {"id": "b", "type": "Erosion2"},
                {"id": "c", "type": "Terrace"},
            ],
            "connections": [
                {"from": "a", "to": "b"},
                {"from": "b", "to": "c"},
                {"from": "c", "to": "a"},
            ],  # Circular
        }

        result = self.call_mcp_tool("validate_and_fix_workflow", {"workflow": circular_workflow})
        self.add_test_result("Circular dependency", result, expected_success=False)

    def test_performance(self):
        """Test performance with timing"""
        print("\n=== Testing Performance ===")

        # Time template creation
        start = time.time()
        result = self.call_mcp_tool(
            "create_gaea2_from_template",
            {"template_name": "basic_terrain", "project_name": "PerformanceTest"},
        )
        elapsed = time.time() - start

        self.add_test_result(f"Template creation time ({elapsed:.2f}s)", result)

        # Time complex validation
        complex_template = Gaea2TestTemplates.create_complex_workflow_template()
        start = time.time()
        result = self.call_mcp_tool(
            "validate_and_fix_workflow",
            {
                "workflow": {
                    "nodes": complex_template["nodes"],
                    "connections": complex_template["connections"],
                }
            },
        )
        elapsed = time.time() - start

        self.add_test_result(f"Complex validation time ({elapsed:.2f}s)", result)

    def generate_report(self):
        """Generate a comprehensive test report"""
        print("\n" + "=" * 60)
        print("GAEA2 MCP COMPREHENSIVE TEST REPORT")
        print("=" * 60)

        summary = self.results["summary"]
        print(f"\nTotal Tests: {summary['total']}")
        print(f"Passed: {summary['passed']} ({summary['passed']/max(summary['total'],1)*100:.1f}%)")
        print(f"Failed: {summary['failed']}")

        if summary["failed"] > 0:
            print("\nFailed Tests:")
            for test in self.results["tests"]:
                if not test["passed"]:
                    print(f"  - {test['name']}")
                    if "error" in test["result"]:
                        print(f"    Error: {test['result']['error']}")

        # Save detailed report
        report_file = f"gaea2_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\nDetailed report saved to: {report_file}")

        # Knowledge validation summary
        print("\n=== Knowledge Validation Summary ===")
        print("Based on the tests, here are findings about our Gaea2 knowledge:")

        # Check which node types worked
        working_nodes = set()
        failed_nodes = set()

        for test in self.results["tests"]:
            if "workflow" in str(test):
                if test["passed"]:
                    # Extract node types from successful tests
                    if "result" in test and "project" in test["result"]:
                        workflow = test["result"]["project"].get("workflow", {})
                        for node in workflow.get("nodes", []):
                            working_nodes.add(node.get("type"))
                else:
                    # Extract node types from failed tests
                    if "parameters" in test.get("result", {}):
                        workflow = test["result"]["parameters"].get("workflow", {})
                        for node in workflow.get("nodes", []):
                            failed_nodes.add(node.get("type"))

        if working_nodes:
            print(f"\nConfirmed working node types ({len(working_nodes)}):")
            for node in sorted(working_nodes):
                print(f"  ✓ {node}")

        if failed_nodes - working_nodes:
            print("\nPotentially problematic node types:")
            for node in sorted(failed_nodes - working_nodes):
                print(f"  ? {node}")

        return summary["failed"] == 0

    def run_all_tests(self):
        """Run all tests"""
        print("Starting Gaea2 MCP Comprehensive Testing...")
        print(f"Server: {self.server_url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Run test suites
        self.test_health_check()
        self.test_builtin_templates()
        self.test_template_creation()
        self.test_error_recovery()
        self.test_optimization()
        self.test_node_suggestions()
        self.test_workflow_analysis()
        self.test_edge_cases()
        self.test_performance()

        # Generate report
        return self.generate_report()


def main():
    """Run comprehensive Gaea2 testing"""
    tester = Gaea2ComprehensiveTester()
    success = tester.run_all_tests()

    # Exit with appropriate code
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
