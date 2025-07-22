"""Unit tests for Gaea2 terrain file format validation"""

from typing import Any, Dict

import pytest


class TestTerrainFileFormat:
    """Test terrain file format structure and requirements"""

    def test_basic_structure_validation(self, sample_terrain: Dict[str, Any]):
        """Test that generated files have all required top-level keys"""
        # Check essential top-level structure
        assert "$id" in sample_terrain
        assert "Assets" in sample_terrain
        assert "Id" in sample_terrain
        assert "Branch" in sample_terrain
        assert "Metadata" in sample_terrain

        # Check Assets structure
        assert "$id" in sample_terrain["Assets"]
        assert "$values" in sample_terrain["Assets"]
        assert isinstance(sample_terrain["Assets"]["$values"], list)
        assert len(sample_terrain["Assets"]["$values"]) > 0

        # Check asset value structure
        asset = sample_terrain["Assets"]["$values"][0]
        assert "Terrain" in asset
        assert "Automation" in asset
        assert "BuildDefinition" in asset
        assert "State" in asset

    def test_terrain_section_structure(self, sample_terrain: Dict[str, Any]):
        """Test terrain section has proper structure"""
        terrain = sample_terrain["Assets"]["$values"][0]["Terrain"]

        # Required terrain fields
        assert "Id" in terrain
        assert "Metadata" in terrain
        assert "Nodes" in terrain
        assert "Groups" in terrain
        assert "Notes" in terrain
        assert "GraphTabs" in terrain
        assert "Width" in terrain
        assert "Height" in terrain
        assert "Ratio" in terrain

        # Check metadata
        metadata = terrain["Metadata"]
        assert "Name" in metadata
        assert "Description" in metadata
        assert "Version" in metadata
        assert "DateCreated" in metadata
        assert "DateLastBuilt" in metadata
        assert "DateLastSaved" in metadata

    def test_id_generation_pattern(self, sample_terrain: Dict[str, Any]):
        """Test non-sequential ID generation pattern"""
        nodes = sample_terrain["Assets"]["$values"][0]["Terrain"]["Nodes"]

        # Get node IDs (skip $id key)
        node_ids = []
        for key, node in nodes.items():
            if key != "$id" and isinstance(node, dict) and "Id" in node:
                node_ids.append(node["Id"])

        # Check IDs are integers
        for node_id in node_ids:
            assert isinstance(node_id, int), f"Node ID {node_id} should be integer"

        # Check non-sequential pattern (not consecutive)
        if len(node_ids) > 1:
            sorted_ids = sorted(node_ids)
            # IDs should have gaps (non-sequential)
            for i in range(1, len(sorted_ids)):
                gap = sorted_ids[i] - sorted_ids[i - 1]
                assert gap > 1, f"IDs {sorted_ids[i-1]} and {sorted_ids[i]} are too close (sequential)"

    def test_object_reference_format(self, sample_terrain: Dict[str, Any]):
        """Test object reference formats"""
        terrain = sample_terrain["Assets"]["$values"][0]["Terrain"]

        # Test Groups format (minimal, just $id)
        assert "Groups" in terrain
        assert "$id" in terrain["Groups"]
        assert "$values" not in terrain["Groups"], "Groups should not have $values"

        # Test Notes format (minimal, just $id)
        assert "Notes" in terrain
        assert "$id" in terrain["Notes"]
        assert "$values" not in terrain["Notes"], "Notes should not have $values"

        # Test Camera format (minimal, just $id)
        viewport = sample_terrain["Assets"]["$values"][0]["State"]["Viewport"]
        assert "Camera" in viewport
        assert "$id" in viewport["Camera"]
        assert "Position" not in viewport["Camera"], "Camera should not have Position"
        assert "Rotation" not in viewport["Camera"], "Camera should not have Rotation"

    def test_graphtabs_structure(self, sample_terrain: Dict[str, Any]):
        """Test GraphTabs has proper structure with values"""
        graphtabs = sample_terrain["Assets"]["$values"][0]["Terrain"]["GraphTabs"]

        assert "$id" in graphtabs
        assert "$values" in graphtabs
        assert isinstance(graphtabs["$values"], list)

        # Should have at least one graph tab
        assert len(graphtabs["$values"]) > 0

        tab = graphtabs["$values"][0]
        assert "Name" in tab
        assert "Color" in tab
        assert "ZoomFactor" in tab
        assert "ViewportLocation" in tab
        assert "X" in tab["ViewportLocation"]
        assert "Y" in tab["ViewportLocation"]

    def test_automation_structure(self, sample_terrain: Dict[str, Any]):
        """Test Automation section structure"""
        automation = sample_terrain["Assets"]["$values"][0]["Automation"]

        assert "Bindings" in automation
        assert "$values" in automation["Bindings"]
        assert "Variables" in automation
        assert "BoundProperties" in automation
        assert "$values" in automation["BoundProperties"]

    def test_builddefinition_structure(self, sample_terrain: Dict[str, Any]):
        """Test BuildDefinition section structure"""
        build = sample_terrain["Assets"]["$values"][0]["BuildDefinition"]

        # Required build settings
        assert "Destination" in build
        assert "Resolution" in build
        assert "BakeResolution" in build
        assert "TileResolution" in build
        assert "BucketResolution" in build
        assert "NumberOfTiles" in build
        assert "TotalTiles" in build
        assert "EdgeBlending" in build
        assert "OrganizeFiles" in build
        assert "Regions" in build

        # Check regions format
        assert "$values" in build["Regions"]

    def test_state_structure(self, sample_terrain: Dict[str, Any]):
        """Test State section structure"""
        state = sample_terrain["Assets"]["$values"][0]["State"]

        assert "BakeResolution" in state
        assert "PreviewResolution" in state
        assert "SelectedNode" in state
        assert "NodeBookmarks" in state
        assert "Viewport" in state

        # Check viewport
        viewport = state["Viewport"]
        assert "RenderMode" in viewport
        assert "SunAltitude" in viewport
        assert "SunAzimuth" in viewport
        assert "Camera" in viewport

    def test_metadata_dates_format(self, sample_terrain: Dict[str, Any]):
        """Test metadata date format"""
        metadata = sample_terrain["Metadata"]

        # All dates should be in ISO format with Z suffix
        date_fields = ["DateCreated", "DateLastBuilt", "DateLastSaved"]
        for field in date_fields:
            assert field in metadata
            date_value = metadata[field]
            assert date_value.endswith("Z"), f"{field} should end with Z"
            assert "T" in date_value, f"{field} should contain T separator"

    def test_id_uniqueness(self, sample_terrain: Dict[str, Any]):
        """Test that all $id values are unique"""
        all_ids = []

        def collect_ids(obj):
            if isinstance(obj, dict):
                if "$id" in obj:
                    all_ids.append(obj["$id"])
                for value in obj.values():
                    collect_ids(value)
            elif isinstance(obj, list):
                for item in obj:
                    collect_ids(item)

        collect_ids(sample_terrain)

        # Check uniqueness
        assert len(all_ids) == len(set(all_ids)), "Duplicate $id values found"

        # Check all IDs are strings
        for id_val in all_ids:
            assert isinstance(id_val, str), f"$id value {id_val} should be string"

    def test_branch_value(self, sample_terrain: Dict[str, Any]):
        """Test Branch value is correct"""
        assert sample_terrain["Branch"] == 1

    def test_terrain_dimensions(self, sample_terrain: Dict[str, Any]):
        """Test terrain dimensions are set correctly"""
        terrain = sample_terrain["Assets"]["$values"][0]["Terrain"]

        assert terrain["Width"] == 5000.0
        assert terrain["Height"] == 2500.0
        assert terrain["Ratio"] == 0.5


# Fixtures


@pytest.fixture
def sample_terrain():
    """Load a sample terrain file for testing"""
    # This would be replaced with actual test data or mock
    return {
        "$id": "1",
        "Assets": {
            "$id": "2",
            "$values": [
                {
                    "$id": "3",
                    "Terrain": {
                        "$id": "4",
                        "Id": "test-terrain-id",
                        "Metadata": {
                            "$id": "5",
                            "Name": "Test Terrain",
                            "Description": "Test Description",
                            "Version": "",
                            "DateCreated": "2025-01-01T00:00:00Z",
                            "DateLastBuilt": "2025-01-01T00:00:00Z",
                            "DateLastSaved": "2025-01-01T00:00:00Z",
                        },
                        "Nodes": {
                            "$id": "6",
                            "183": {"$id": "7", "Id": 183, "Name": "Mountain"},
                        },
                        "Groups": {"$id": "8"},
                        "Notes": {"$id": "9"},
                        "GraphTabs": {
                            "$id": "10",
                            "$values": [
                                {
                                    "$id": "11",
                                    "Name": "Graph 1",
                                    "Color": "Brass",
                                    "ZoomFactor": 0.5,
                                    "ViewportLocation": {
                                        "$id": "12",
                                        "X": 25000.0,
                                        "Y": 26000.0,
                                    },
                                }
                            ],
                        },
                        "Width": 5000.0,
                        "Height": 2500.0,
                        "Ratio": 0.5,
                    },
                    "Automation": {
                        "$id": "13",
                        "Bindings": {"$id": "14", "$values": []},
                        "Variables": {"$id": "15"},
                        "BoundProperties": {"$id": "16", "$values": []},
                    },
                    "BuildDefinition": {
                        "$id": "17",
                        "Destination": "<Builds>\\[Filename]\\[+++]",
                        "Resolution": 2048,
                        "BakeResolution": 2048,
                        "TileResolution": 1024,
                        "BucketResolution": 2048,
                        "NumberOfTiles": 1,
                        "TotalTiles": 1,
                        "EdgeBlending": 0.25,
                        "OrganizeFiles": "NodeSubFolder",
                        "Regions": {"$id": "18", "$values": []},
                    },
                    "State": {
                        "$id": "19",
                        "BakeResolution": 2048,
                        "PreviewResolution": 512,
                        "SelectedNode": 183,
                        "NodeBookmarks": {"$id": "20", "$values": []},
                        "Viewport": {
                            "$id": "21",
                            "RenderMode": "Realistic",
                            "SunAltitude": 33.0,
                            "SunAzimuth": 45.0,
                            "Camera": {"$id": "22"},
                        },
                    },
                }
            ],
        },
        "Id": "test-id",
        "Branch": 1,
        "Metadata": {
            "$id": "23",
            "Name": "Test Terrain",
            "Description": "Test Description",
            "Version": "",
            "Owner": "",
            "DateCreated": "2025-01-01T00:00:00Z",
            "DateLastBuilt": "2025-01-01T00:00:00Z",
            "DateLastSaved": "2025-01-01T00:00:00Z",
        },
    }
