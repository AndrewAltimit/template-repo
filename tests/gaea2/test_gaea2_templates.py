#!/usr/bin/env python3
"""
Test Gaea2 MCP server with various template maps to identify schema/validation gaps.
This script creates diverse terrain templates and analyzes the results.
"""
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tools.mcp.core import MCPClient  # noqa: E402


class Gaea2TemplateTester:
    """Test Gaea2 MCP implementation with various templates."""

    def __init__(self):
        # Use remote Gaea2 MCP server
        self.client = MCPClient(base_url="http://192.168.0.152:8000")
        self.results = []
        self.test_dir = "outputs/tests/gaea2_templates"
        os.makedirs(self.test_dir, exist_ok=True)

    def setup(self):
        """Initialize the MCP client."""
        # Check if server is healthy
        if not self.client.health_check():
            raise RuntimeError("MCP server is not available at http://192.168.0.152:8000")
        print("✅ Remote Gaea2 MCP server is healthy")

    def cleanup(self):
        """Clean up resources."""
        # No cleanup needed for HTTP client
        pass

    def create_template(self, name: str, workflow: Dict[str, Any], description: str) -> Tuple[bool, str, Any]:
        """
        Create a Gaea2 template and capture results.

        Returns:
            Tuple of (success, output_path, result_data)
        """
        print(f"\n{'='*60}")
        print(f"Creating template: {name}")
        print(f"Description: {description}")
        print(f"{'='*60}")

        try:
            result = self.client.execute_tool(
                "create_gaea2_project",
                {
                    "project_name": name,
                    "workflow": workflow,
                    "output_path": self.test_dir,
                    "auto_validate": True,  # Test with validation enabled
                },
            )

            success = result.get("success", False)
            output_path = result.get("output_path", "")

            # Store result for analysis
            self.results.append(
                {
                    "name": name,
                    "description": description,
                    "success": success,
                    "output_path": output_path,
                    "validation_results": result.get("validation_results", {}),
                    "errors": result.get("errors", []),
                    "warnings": result.get("warnings", []),
                    "workflow": workflow,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            if success:
                print(f"✅ Successfully created: {output_path}")
                if result.get("validation_results"):
                    print(f"Validation summary: {json.dumps(result['validation_results'], indent=2)}")
            else:
                print("❌ Failed to create template")
                if result.get("error"):
                    print(f"Error: {result['error']}")

            return success, output_path, result

        except Exception as e:
            print(f"❌ Exception occurred: {str(e)}")
            self.results.append(
                {
                    "name": name,
                    "description": description,
                    "success": False,
                    "error": str(e),
                    "workflow": workflow,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return False, "", {"error": str(e)}

    def test_basic_terrain(self):
        """Test 1: Basic terrain with simple erosion."""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "Primitive", "properties": {"Type": "Gradient"}},
                {"id": "n2", "type": "FractalTerraces", "properties": {"Octaves": 4}},
                {"id": "n3", "type": "Erosion", "properties": {"Duration": 15}},
                {"id": "n4", "type": "SatMap", "properties": {}},
                {
                    "id": "n5",
                    "type": "Export",
                    "properties": {"Format": "PNG"},
                    "save_definition": {
                        "filename": "basic_terrain",
                        "format": "PNG",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                },
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "In",
                },
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n4",
                    "to_port": "In",
                },
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n5",
                    "to_port": "In",
                },
            ],
        }

        return self.create_template(
            "basic_terrain",
            workflow,
            "Basic terrain with gradient, terraces, and erosion",
        )

    def test_complex_multibiome(self):
        """Test 2: Complex multi-biome terrain."""
        workflow = {
            "nodes": [
                # Height generation
                {"id": "n1", "type": "Mountain", "properties": {"Height": 2000}},
                {"id": "n2", "type": "Primitive", "properties": {"Type": "Perlin"}},
                {"id": "n3", "type": "Combine", "properties": {"Method": "Add"}},
                # Biome masks
                {
                    "id": "n4",
                    "type": "SlopeSelector",
                    "properties": {"MinAngle": 0, "MaxAngle": 30},
                },
                {
                    "id": "n5",
                    "type": "HeightSelector",
                    "properties": {"Min": 0, "Max": 500},
                },
                {"id": "n6", "type": "Combine", "properties": {"Method": "Multiply"}},
                # Erosion variants
                {"id": "n7", "type": "Erosion2", "properties": {"RockSoftness": 0.5}},
                {"id": "n8", "type": "Fluvial", "properties": {"Amount": 0.7}},
                {"id": "n9", "type": "Thermal", "properties": {"Intensity": 0.5}},
                # Final composition
                {"id": "n10", "type": "Layers", "properties": {}},
                {"id": "n11", "type": "SatMap", "properties": {"Style": "Terrain"}},
                {
                    "id": "n12",
                    "type": "Export",
                    "properties": {"Format": "EXR"},
                    "save_definition": {
                        "filename": "multibiome",
                        "format": "EXR",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                # Height network
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "in1",
                },
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "in2",
                },
                # Biome mask network
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n4",
                    "to_port": "In",
                },
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n5",
                    "to_port": "In",
                },
                {
                    "from_node": "n4",
                    "from_port": "Out",
                    "to_node": "n6",
                    "to_port": "in1",
                },
                {
                    "from_node": "n5",
                    "from_port": "Out",
                    "to_node": "n6",
                    "to_port": "in2",
                },
                # Erosion application
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n7",
                    "to_port": "In",
                },
                {
                    "from_node": "n7",
                    "from_port": "Out",
                    "to_node": "n8",
                    "to_port": "In",
                },
                {
                    "from_node": "n8",
                    "from_port": "Out",
                    "to_node": "n9",
                    "to_port": "In",
                },
                # Final composition
                {
                    "from_node": "n9",
                    "from_port": "Out",
                    "to_node": "n10",
                    "to_port": "In",
                },
                {
                    "from_node": "n6",
                    "from_port": "Out",
                    "to_node": "n10",
                    "to_port": "mask",
                },
                {
                    "from_node": "n10",
                    "from_port": "Out",
                    "to_node": "n11",
                    "to_port": "In",
                },
                {
                    "from_node": "n10",
                    "from_port": "Out",
                    "to_node": "n12",
                    "to_port": "In",
                },
            ],
        }

        return self.create_template(
            "complex_multibiome",
            workflow,
            "Complex multi-biome terrain with layered erosion and masking",
        )

    def test_volcanic_terrain(self):
        """Test 3: Volcanic terrain with lava flows."""
        workflow = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Crater",
                    "properties": {"Radius": 500, "Depth": 300},
                },
                {"id": "n2", "type": "Mountain", "properties": {"Height": 3000}},
                {"id": "n3", "type": "Combine", "properties": {"Method": "Max"}},
                {"id": "n4", "type": "LavaFlow", "properties": {"Temperature": 1200}},
                {
                    "id": "n5",
                    "type": "ThermalShatter",
                    "properties": {"Intensity": 0.8},
                },
                {"id": "n6", "type": "Sediment", "properties": {"Amount": 0.3}},
                {"id": "n7", "type": "SatMap", "properties": {"Style": "Volcanic"}},
                {
                    "id": "n8",
                    "type": "Export",
                    "properties": {"Format": "PNG"},
                    "save_definition": {
                        "filename": "volcanic",
                        "format": "PNG",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "in1",
                },
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "in2",
                },
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n4",
                    "to_port": "In",
                },
                {
                    "from_node": "n4",
                    "from_port": "Out",
                    "to_node": "n5",
                    "to_port": "In",
                },
                {
                    "from_node": "n5",
                    "from_port": "Out",
                    "to_node": "n6",
                    "to_port": "In",
                },
                {
                    "from_node": "n6",
                    "from_port": "Out",
                    "to_node": "n7",
                    "to_port": "In",
                },
                {
                    "from_node": "n6",
                    "from_port": "Out",
                    "to_node": "n8",
                    "to_port": "In",
                },
            ],
        }

        return self.create_template(
            "volcanic_terrain",
            workflow,
            "Volcanic terrain with crater, lava flows, and thermal effects",
        )

    def test_coastal_water(self):
        """Test 4: Coastal terrain with water bodies."""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "Island", "properties": {"Size": 2000}},
                {"id": "n2", "type": "Beach", "properties": {"Width": 100}},
                {"id": "n3", "type": "SeaLevel", "properties": {"Level": 0}},
                {"id": "n4", "type": "Coast", "properties": {"Erosion": 0.5}},
                {"id": "n5", "type": "Lakes", "properties": {"Count": 3}},
                {"id": "n6", "type": "Rivers", "properties": {"Count": 2}},
                {"id": "n7", "type": "Combine", "properties": {"Method": "Min"}},
                {"id": "n8", "type": "SatMap", "properties": {"Style": "Coastal"}},
                {
                    "id": "n9",
                    "type": "Export",
                    "properties": {"Format": "PNG"},
                    "save_definition": {
                        "filename": "coastal",
                        "format": "PNG",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                },
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "In",
                },
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n4",
                    "to_port": "In",
                },
                {
                    "from_node": "n4",
                    "from_port": "Out",
                    "to_node": "n5",
                    "to_port": "In",
                },
                {
                    "from_node": "n5",
                    "from_port": "Out",
                    "to_node": "n6",
                    "to_port": "In",
                },
                {
                    "from_node": "n6",
                    "from_port": "Out",
                    "to_node": "n7",
                    "to_port": "in1",
                },
                {
                    "from_node": "n3",
                    "from_port": "water",
                    "to_node": "n7",
                    "to_port": "in2",
                },
                {
                    "from_node": "n7",
                    "from_port": "Out",
                    "to_node": "n8",
                    "to_port": "In",
                },
                {
                    "from_node": "n7",
                    "from_port": "Out",
                    "to_node": "n9",
                    "to_port": "In",
                },
            ],
        }

        return self.create_template(
            "coastal_water",
            workflow,
            "Coastal terrain with beaches, water bodies, and erosion",
        )

    def test_edge_cases(self):
        """Test 5: Edge cases to stress-test validation."""
        # Test various problematic scenarios
        edge_cases = []

        # Edge case 1: Duplicate connections
        workflow1 = {
            "nodes": [
                {"id": "n1", "type": "Primitive", "properties": {}},
                {"id": "n2", "type": "Erosion", "properties": {}},
                {
                    "id": "n3",
                    "type": "Export",
                    "properties": {"Format": "PNG"},
                    "save_definition": {
                        "filename": "edge_test",
                        "format": "PNG",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                },
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                },  # Duplicate!
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "In",
                },
            ],
        }
        edge_cases.append(
            (
                "edge_duplicate_connections",
                workflow1,
                "Workflow with duplicate connections",
            )
        )

        # Edge case 2: Missing essential nodes
        workflow2 = {
            "nodes": [
                {"id": "n1", "type": "Mountain", "properties": {}},
                {"id": "n2", "type": "Erosion", "properties": {}},
                # Missing Export and SatMap!
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                }
            ],
        }
        edge_cases.append(("edge_missing_essentials", workflow2, "Workflow missing essential nodes"))

        # Edge case 3: Invalid property values
        workflow3 = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Primitive",
                    "properties": {"Type": "InvalidType"},
                },
                {
                    "id": "n2",
                    "type": "Erosion",
                    "properties": {"Duration": -50},
                },  # Negative duration!
                {
                    "id": "n3",
                    "type": "Mountain",
                    "properties": {"Height": 999999},
                },  # Extreme height!
                {
                    "id": "n4",
                    "type": "Export",
                    "properties": {"Format": "PNG"},
                    "save_definition": {
                        "filename": "edge_invalid",
                        "format": "PNG",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                },
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "In",
                },
                {
                    "from_node": "n3",
                    "from_port": "Out",
                    "to_node": "n4",
                    "to_port": "In",
                },
            ],
        }
        edge_cases.append(
            (
                "edge_invalid_properties",
                workflow3,
                "Workflow with invalid property values",
            )
        )

        # Edge case 4: Circular dependencies
        workflow4 = {
            "nodes": [
                {"id": "n1", "type": "Combine", "properties": {}},
                {"id": "n2", "type": "Blur", "properties": {}},
                {
                    "id": "n3",
                    "type": "Export",
                    "properties": {"Format": "PNG"},
                    "save_definition": {
                        "filename": "edge_test",
                        "format": "PNG",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                },
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n1",
                    "to_port": "in1",
                },  # Circular!
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "In",
                },
            ],
        }
        edge_cases.append(("edge_circular_deps", workflow4, "Workflow with circular dependencies"))

        # Edge case 5: Unknown node types
        workflow5 = {
            "nodes": [
                {"id": "n1", "type": "UnknownNodeType", "properties": {}},
                {"id": "n2", "type": "AnotherUnknown", "properties": {}},
                {
                    "id": "n3",
                    "type": "Export",
                    "properties": {"Format": "PNG"},
                    "save_definition": {
                        "filename": "edge_test",
                        "format": "PNG",
                        "enabled": True,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "n1",
                    "from_port": "Out",
                    "to_node": "n2",
                    "to_port": "In",
                },
                {
                    "from_node": "n2",
                    "from_port": "Out",
                    "to_node": "n3",
                    "to_port": "In",
                },
            ],
        }
        edge_cases.append(("edge_unknown_nodes", workflow5, "Workflow with unknown node types"))

        # Run all edge cases
        for name, workflow, description in edge_cases:
            self.create_template(name, workflow, description)

    def test_from_templates(self):
        """Test creating projects from built-in templates."""
        templates = [
            "mountain_range",
            "volcanic_island",
            "canyon_system",
            "coastal_cliffs",
            "arctic_terrain",
        ]

        for template in templates:
            print(f"\n{'='*60}")
            print(f"Testing template: {template}")
            print(f"{'='*60}")

            try:
                result = self.client.execute_tool(
                    "create_gaea2_from_template",
                    {
                        "template_name": template,
                        "project_name": f"test_{template}",
                        "output_path": self.test_dir,
                    },
                )

                self.results.append(
                    {
                        "name": f"template_{template}",
                        "description": f"Project from template: {template}",
                        "success": result.get("success", False),
                        "output_path": result.get("output_path", ""),
                        "template_used": template,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                print(f"❌ Failed to create from template: {str(e)}")
                self.results.append(
                    {
                        "name": f"template_{template}",
                        "description": f"Project from template: {template}",
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

    def analyze_results(self):
        """Analyze test results and identify issues."""
        print(f"\n{'='*80}")
        print("TEST RESULTS ANALYSIS")
        print(f"{'='*80}")

        total_tests = len(self.results)
        successful = sum(1 for r in self.results if r.get("success"))
        failed = total_tests - successful

        print("\nSummary:")
        print(f"  Total tests: {total_tests}")
        print(f"  Successful: {successful} ({successful/total_tests*100:.1f}%)")
        print(f"  Failed: {failed} ({failed/total_tests*100:.1f}%)")

        # Analyze validation issues
        validation_issues = {}
        # property_issues = {}  # Reserved for future use
        # connection_issues = {}  # Reserved for future use
        # node_issues = {}  # Reserved for future use

        for result in self.results:
            if not result.get("success"):
                print(f"\n❌ Failed: {result['name']}")
                if "error" in result:
                    print(f"   Error: {result['error']}")

            # Collect validation data
            if "validation_results" in result:
                val_results = result["validation_results"]

                # Track issues fixed
                if "issues_fixed" in val_results:
                    for issue in val_results["issues_fixed"]:
                        issue_type = issue.get("type", "unknown")
                        if issue_type not in validation_issues:
                            validation_issues[issue_type] = []
                        validation_issues[issue_type].append({"test": result["name"], "issue": issue})

                # Track warnings
                if "warnings" in val_results:
                    for warning in val_results["warnings"]:
                        print(f"   ⚠️  Warning in {result['name']}: {warning}")

        # Report common issues
        if validation_issues:
            print("\n\nCommon Validation Issues Fixed:")
            for issue_type, occurrences in validation_issues.items():
                print(f"\n  {issue_type}: {len(occurrences)} occurrences")
                for occ in occurrences[:3]:  # Show first 3 examples
                    print(f"    - In {occ['test']}: {occ['issue'].get('description', 'No description')}")

        # Save detailed results
        results_file = os.path.join(self.test_dir, "test_results.json")
        with open(results_file, "w") as f:
            json.dump(
                {
                    "summary": {
                        "total_tests": total_tests,
                        "successful": successful,
                        "failed": failed,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "validation_issues": validation_issues,
                    "detailed_results": self.results,
                },
                f,
                indent=2,
            )

        print(f"\n\nDetailed results saved to: {results_file}")

        # Recommendations
        print("\n\nRecommendations:")
        print("1. Schema Updates Needed:")

        # Check for unknown nodes
        unknown_nodes = set()
        for result in self.results:
            if "error" in result and "unknown node type" in result["error"].lower():
                # Extract node type from error
                unknown_nodes.add(result["name"])

        if unknown_nodes:
            print(f"   - Add support for unknown node types found in: {', '.join(unknown_nodes)}")
        else:
            print("   - No unknown node types encountered ✅")

        print("\n2. Validation Improvements:")
        if validation_issues:
            print(f"   - Most common issue type: {max(validation_issues, key=lambda k: len(validation_issues[k]))}")
            print("   - Consider stricter validation for these areas")
        else:
            print("   - Validation appears comprehensive ✅")

        print("\n3. Property Range Validation:")
        print("   - Review property constraints based on edge case results")
        print("   - Consider adding more intelligent defaults")

    def run_all_tests(self):
        """Run all template tests."""
        self.setup()

        try:
            # Run core template tests
            self.test_basic_terrain()
            self.test_complex_multibiome()
            self.test_volcanic_terrain()
            self.test_coastal_water()
            self.test_edge_cases()

            # Test built-in templates
            self.test_from_templates()

            # Analyze results
            self.analyze_results()

        finally:
            self.cleanup()


def main():
    """Main entry point."""
    tester = Gaea2TemplateTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
