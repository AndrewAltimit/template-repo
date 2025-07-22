#!/usr/bin/env python3
"""
Test the enhanced Gaea2 validation that checks:
1. Node type validity
2. Property count limits for problematic nodes
3. Workflow connectivity
4. Actual file opening in Gaea2
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest  # noqa: E402

from tools.mcp.gaea2.validation.validator import Gaea2Validator  # noqa: E402


class TestEnhancedValidation:
    """Test the enhanced validation features"""

    @pytest.fixture
    def validator(self):
        """Create a validator instance"""
        return Gaea2Validator()

    @pytest.mark.asyncio
    async def test_invalid_node_type_detection(self, validator):
        """Test that invalid node types are detected"""
        workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"x": 0, "y": 0}},
                {"id": "2", "type": "InvalidNodeType", "position": {"x": 100, "y": 0}},
                {
                    "id": "3",
                    "type": "Islands",
                    "position": {"x": 200, "y": 0},
                },  # Wrong: should be Island
            ],
            "connections": [],
        }

        result = await validator.validate_and_fix(workflow)

        assert not result["valid"]
        assert len(result["errors"]) >= 2
        assert any("Invalid node type 'InvalidNodeType'" in err for err in result["errors"])
        assert any("Invalid node type 'Islands'" in err for err in result["errors"])

    @pytest.mark.asyncio
    async def test_property_count_limit_detection(self, validator):
        """Test that nodes with too many properties are detected"""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Snow",
                    "position": {"x": 0, "y": 0},
                    "properties": {
                        "Duration": 0.5,
                        "SnowLine": 0.7,
                        "Melt": 0.3,
                        "Intensity": 0.8,  # 4th property
                        "Coverage": 0.9,  # 5th property
                        "Depth": 0.6,  # 6th property
                        "Wetness": 0.4,  # 7th property
                        "Temperature": -5,  # 8th property
                    },
                },
                {
                    "id": "2",
                    "type": "Mountain",  # Not limited
                    "position": {"x": 100, "y": 0},
                    "properties": {
                        "Height": 0.8,
                        "Scale": 1.5,
                        "Peaks": 4,
                        "Style": "Alpine",
                        "Bulk": "High",
                        "Seed": 12345,
                        "X": 0.5,
                        "Y": 0.5,
                    },
                },
            ],
            "connections": [],
        }

        result = await validator.validate_and_fix(workflow)

        assert not result["valid"]
        assert any("Snow" in err and "8 properties" in err and "<= 3 properties" in err for err in result["errors"])
        # Mountain should not have property limit errors
        assert not any("Mountain" in err and "properties" in err for err in result["errors"])

    @pytest.mark.asyncio
    async def test_property_count_limit_fixing(self, validator):
        """Test that nodes with too many properties are fixed"""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Snow",
                    "position": {"x": 0, "y": 0},
                    "properties": {
                        "Duration": 0.5,
                        "SnowLine": 0.7,
                        "Melt": 0.3,
                        "Intensity": 0.8,
                        "Coverage": 0.9,
                        "Depth": 0.6,
                        "Wetness": 0.4,
                        "Temperature": -5,
                    },
                }
            ],
            "connections": [],
        }

        result = await validator.validate_and_fix(workflow)

        # Check that the fix was applied
        assert result["fixed"]
        assert any("Limited Snow node to 3 essential properties" in fix for fix in result["fixes_applied"])

        # Check that the node now has only 3 properties
        fixed_node = result["workflow"]["nodes"][0]
        assert len(fixed_node["properties"]) == 3
        # Should keep the essential properties
        assert "Duration" in fixed_node["properties"]
        assert "SnowLine" in fixed_node["properties"]
        assert "Melt" in fixed_node["properties"]

    @pytest.mark.asyncio
    async def test_workflow_connectivity_validation(self, validator):
        """Test that orphaned nodes are detected"""
        workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"x": 0, "y": 0}},
                {"id": "2", "type": "Erosion2", "position": {"x": 100, "y": 0}},
                {
                    "id": "3",
                    "type": "Volcano",
                    "position": {"x": 200, "y": 0},
                },  # Orphaned
                {"id": "4", "type": "SatMap", "position": {"x": 300, "y": 0}},
                {"id": "5", "type": "Export", "position": {"x": 400, "y": 0}},
            ],
            "connections": [
                {
                    "source": "1",
                    "source_port": "Out",
                    "target": "2",
                    "target_port": "In",
                },
                {
                    "source": "2",
                    "source_port": "Out",
                    "target": "4",
                    "target_port": "In",
                },
                {
                    "source": "4",
                    "source_port": "Out",
                    "target": "5",
                    "target_port": "In",
                },
            ],
        }

        result = await validator.validate_and_fix(workflow)

        # Should have warnings about orphaned Volcano node
        assert len(result.get("warnings", [])) > 0
        assert any("Volcano" in warn and "not connected" in warn for warn in result["warnings"])

    @pytest.mark.asyncio
    async def test_invalid_connections_detection(self, validator):
        """Test that connections to non-existent nodes are detected"""
        workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"x": 0, "y": 0}},
                {"id": "2", "type": "Erosion2", "position": {"x": 100, "y": 0}},
            ],
            "connections": [
                {
                    "source": "1",
                    "source_port": "Out",
                    "target": "2",
                    "target_port": "In",
                },
                {
                    "source": "2",
                    "source_port": "Out",
                    "target": "99",
                    "target_port": "In",
                },  # Invalid target
                {
                    "source": "88",
                    "source_port": "Out",
                    "target": "1",
                    "target_port": "In",
                },  # Invalid source
            ],
        }

        result = await validator.validate_and_fix(workflow)

        assert not result["valid"]
        assert any("non-existent target node: 99" in err for err in result["errors"])
        assert any("non-existent source node: 88" in err for err in result["errors"])

    @pytest.mark.asyncio
    async def test_comprehensive_validation_with_file_test(self, validator):
        """Test the comprehensive validation including file opening test"""

        # This test requires a mock CLI runner since we can't actually run Gaea2
        class MockCLIRunner:
            async def run_gaea2_project(self, project_path, resolution, format, timeout):
                # Simulate a file that can't open
                return {
                    "success": False,
                    "stdout": "Error: Failed to load terrain file\nUnknown node type 'InvalidNode'",
                    "stderr": "",
                }

        workflow = {
            "nodes": [{"id": "1", "type": "Mountain", "position": {"x": 0, "y": 0}}],
            "connections": [],
        }

        result = await validator.validate_workflow_comprehensive(
            workflow,
            project_path="/tmp/test.terrain",
            cli_runner=MockCLIRunner(),
            test_opening=True,
        )

        assert not result["valid"]
        assert "gaea2_open_test" in result
        assert not result["gaea2_open_test"]["can_open"]
        assert any("File cannot be opened in Gaea2" in err for err in result["errors"])

    @pytest.mark.asyncio
    async def test_valid_workflow(self, validator):
        """Test that a valid workflow passes all checks"""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Mountain",
                    "position": {"x": 0, "y": 0},
                    "properties": {"Height": 0.8, "Scale": 1.5},
                },
                {
                    "id": "2",
                    "type": "Ridge",
                    "position": {"x": 100, "y": 0},
                    "properties": {"Scale": 0.5, "Complexity": 0.7},
                },  # Only 2 properties
                {
                    "id": "3",
                    "type": "Erosion2",
                    "position": {"x": 200, "y": 0},
                    "properties": {"Duration": 0.3},
                },
                {"id": "4", "type": "SatMap", "position": {"x": 300, "y": 0}},
            ],
            "connections": [
                {
                    "source": "1",
                    "source_port": "Out",
                    "target": "2",
                    "target_port": "In",
                },
                {
                    "source": "2",
                    "source_port": "Out",
                    "target": "3",
                    "target_port": "In",
                },
                {
                    "source": "3",
                    "source_port": "Out",
                    "target": "4",
                    "target_port": "In",
                },
            ],
        }

        result = await validator.validate_and_fix(workflow)

        assert result["valid"]
        assert len(result["errors"]) == 0
        # Warnings are informational and don't affect validity
        # Just ensure no errors about unconnected nodes (only Volcano was unconnected in previous test)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
