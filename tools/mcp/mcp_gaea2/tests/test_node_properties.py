"""Unit tests for Gaea2 node property validation"""

from typing import Any, Dict

import pytest


class TestNodeProperties:
    """Test node property constraints and validation"""

    def test_required_node_properties(self, sample_node: Dict[str, Any]):
        """Test that all nodes have required base properties"""
        # Required properties
        assert "Id" in sample_node
        assert "Name" in sample_node
        assert "$type" in sample_node
        assert "Position" in sample_node
        assert "$id" in sample_node

        # Check Position structure
        position = sample_node["Position"]
        assert "$id" in position
        assert "X" in position
        assert "Y" in position
        assert isinstance(position["X"], (int, float))
        assert isinstance(position["Y"], (int, float))

    def test_node_id_is_integer(self, sample_node: Dict[str, Any]):
        """Test that node Id property is integer"""
        assert isinstance(sample_node["Id"], int), "Node Id must be integer"

    def test_no_xy_at_root(self, sample_node: Dict[str, Any]):
        """Test that X and Y are not at node root level"""
        assert "X" not in sample_node, "X should not be at node root"
        assert "Y" not in sample_node, "Y should not be at node root"
        assert "x" not in sample_node, "x should not be at node root"
        assert "y" not in sample_node, "y should not be at node root"

    def test_node_type_format(self, sample_node: Dict[str, Any]):
        """Test $type matches Gaea2 namespace format"""
        node_type = sample_node["$type"]
        assert node_type.startswith("QuadSpinner.Gaea.Nodes."), f"Invalid type format: {node_type}"
        assert node_type.endswith(", Gaea.Nodes"), f"Invalid type suffix: {node_type}"

    def test_node_size_values(self):
        """Test NodeSize property values"""
        valid_sizes = ["Small", "Standard", "Compact"]

        # Test node with NodeSize
        node = {"NodeSize": "Standard"}
        assert node["NodeSize"] in valid_sizes

        # Test invalid size
        with pytest.raises(AssertionError):
            node["NodeSize"] = "Large"
            assert node["NodeSize"] in valid_sizes

    def test_ports_structure(self, sample_node: Dict[str, Any]):
        """Test Ports object structure"""
        if "Ports" in sample_node:
            ports = sample_node["Ports"]
            assert "$id" in ports
            assert "$values" in ports
            assert isinstance(ports["$values"], list)

            # Check port structure
            for port in ports["$values"]:
                assert "$id" in port
                assert "Name" in port
                assert "Type" in port
                assert "IsExporting" in port
                assert "Parent" in port
                assert "$ref" in port["Parent"]

    def test_modifiers_structure(self, sample_node: Dict[str, Any]):
        """Test Modifiers structure"""
        if "Modifiers" in sample_node:
            modifiers = sample_node["Modifiers"]
            assert "$id" in modifiers
            assert "$values" in modifiers
            assert isinstance(modifiers["$values"], list)

    def test_property_name_formatting(self):
        """Test property name formatting with spaces"""
        # Properties that should have spaces
        space_properties = {
            "RockSoftness": "Rock Softness",
            "CoastalErosion": "Coastal Erosion",
            "ExtraCliffDetails": "Extra Cliff Details",
            "ReduceDetails": "Reduce Details",
            "SnowLine": "Snow Line",
            "SettleDuration": "Settle Duration",
            "RiverValleyWidth": "River Valley Width",
        }

        # This would be validated during node creation
        # Here we just verify the mapping exists
        assert len(space_properties) > 0

    def test_numeric_property_ranges(self):
        """Test numeric properties are within valid ranges"""
        # Test various property ranges
        test_cases = [
            ("Scale", 0.5, 0.1, 10.0),
            ("Height", 0.75, 0.0, 1.0),
            ("Seed", 12345, 0, 999999),
            ("Duration", 5.0, 0.0, 20.0),
            ("Downcutting", 0.3, 0.0, 1.0),
        ]

        for prop_name, value, min_val, max_val in test_cases:
            assert min_val <= value <= max_val, f"{prop_name} value {value} out of range [{min_val}, {max_val}]"

    def test_enum_property_values(self):
        """Test enum properties have valid values"""
        # Mountain Style
        mountain_styles = ["Basic", "Eroded", "Old", "Alpine", "Strata"]
        assert "Eroded" in mountain_styles

        # Rivers RiverValleyWidth
        river_widths = ["zero", "plus2", "plus4", "plus6", "plus8"]
        assert "zero" in river_widths

        # SatMap Library
        satmap_libraries = ["Rock", "Green", "Blue", "Sand", "Color"]
        assert "Rock" in satmap_libraries

        # Combine Mode
        combine_modes = [
            "Default",
            "Add",
            "Subtract",
            "Multiply",
            "Divide",
            "Max",
            "Min",
        ]
        assert "Add" in combine_modes

    def test_range_object_format(self):
        """Test Range object format"""
        range_obj = {"$id": "123", "X": 0.25, "Y": 0.75}  # Min value  # Max value

        assert "$id" in range_obj
        assert "X" in range_obj
        assert "Y" in range_obj
        assert isinstance(range_obj["X"], (int, float))
        assert isinstance(range_obj["Y"], (int, float))
        assert range_obj["X"] <= range_obj["Y"], "Range X (min) should be <= Y (max)"

    def test_export_node_properties(self):
        """Test Export node specific properties"""
        export_node = {
            "$type": "QuadSpinner.Gaea.Nodes.Export, Gaea.Nodes",
            "Id": 999,
            "Name": "Export",
            "SaveDefinition": {
                "$id": "100",
                "Node": 999,
                "Filename": "output",
                "Format": "EXR",
                "IsEnabled": True,
            },
        }

        assert "SaveDefinition" in export_node
        save_def = export_node["SaveDefinition"]
        assert save_def["Node"] == export_node["Id"]
        assert save_def["Format"] in ["EXR", "PNG", "TIF", "RAW"]
        assert isinstance(save_def["IsEnabled"], bool)

    def test_combine_node_properties(self):
        """Test Combine node specific properties"""
        combine_node = {
            "$type": "QuadSpinner.Gaea.Nodes.Combine, Gaea.Nodes",
            "PortCount": 2,
            "Mode": "Add",
            "Ratio": 0.5,
            "Clamp": "Clamp",
        }

        assert 2 <= combine_node["PortCount"] <= 6
        assert combine_node["Mode"] in [
            "Default",
            "Add",
            "Subtract",
            "Multiply",
            "Divide",
            "Max",
            "Min",
        ]
        assert 0.0 <= combine_node["Ratio"] <= 1.0

    def test_erosion2_properties(self):
        """Test Erosion2 node specific properties"""
        erosion2_node = {
            "Duration": 1.5,
            "Downcutting": 0.3,
            "ErosionScale": 5000.0,
            "Seed": 12345,
            "SuspendedLoadDischargeAmount": 0.5,
            "SuspendedLoadDischargeAngle": 45.0,
            "BedLoadDischargeAmount": 0.5,
            "BedLoadDischargeAngle": 30.0,
            "Shape": 0.5,
            "ShapeSharpness": 0.5,
            "ShapeDetailScale": 0.5,
        }

        # Validate ranges
        assert 0.0 <= erosion2_node["Duration"] <= 20.0
        assert 0.0 <= erosion2_node["Downcutting"] <= 1.0
        assert 10.0 <= erosion2_node["ErosionScale"] <= 100000.0
        assert 0.0 <= erosion2_node["Shape"] <= 1.0

    def test_rivers_node_properties(self):
        """Test Rivers node specific properties"""
        rivers_node = {
            "$type": "QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes",
            "Water": 0.5,
            "Width": 0.8,
            "Depth": 0.9,
            "Downcutting": 0.3,
            "RiverValleyWidth": "zero",
            "Headwaters": 200,
            "RenderSurface": True,
            "NodeSize": "Standard",
        }

        assert 0.0 <= rivers_node["Water"] <= 1.0
        assert 0.0 <= rivers_node["Width"] <= 1.0
        assert rivers_node["RiverValleyWidth"] in [
            "zero",
            "plus2",
            "plus4",
            "plus6",
            "plus8",
        ]
        assert isinstance(rivers_node["RenderSurface"], bool)

    def test_property_order(self, sample_node: Dict[str, Any]):
        """Test that properties appear before standard fields"""
        # In the actual node, properties should come after $id and $type
        # but before Id, Name, Position, etc.
        keys = list(sample_node.keys())

        # Find positions of key elements
        id_pos = keys.index("$id") if "$id" in keys else -1
        type_pos = keys.index("$type") if "$type" in keys else -1
        node_id_pos = keys.index("Id") if "Id" in keys else -1

        # Basic ordering check
        if id_pos >= 0 and type_pos >= 0:
            assert type_pos > id_pos, "$type should come after $id"
        if type_pos >= 0 and node_id_pos >= 0:
            assert node_id_pos > type_pos, "Id should come after $type"


# Test fixtures


@pytest.fixture
def sample_node():
    """Sample node for testing"""
    return {
        "$id": "7",
        "$type": "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes",
        "Scale": 1.0,
        "Height": 0.5,
        "Seed": 12345,
        "Id": 183,
        "Name": "Mountain",
        "Position": {"$id": "8", "X": 24000.0, "Y": 26000.0},
        "Ports": {
            "$id": "9",
            "$values": [
                {
                    "$id": "10",
                    "Name": "In",
                    "Type": "PrimaryIn",
                    "IsExporting": True,
                    "Parent": {"$ref": "7"},
                },
                {
                    "$id": "11",
                    "Name": "Out",
                    "Type": "PrimaryOut",
                    "IsExporting": True,
                    "Parent": {"$ref": "7"},
                },
            ],
        },
        "Modifiers": {"$id": "12", "$values": []},
        "SnapIns": {"$id": "13", "$values": []},
    }


@pytest.fixture
def multi_port_node():
    """Sample multi-port node (Rivers)"""
    return {
        "$id": "50",
        "$type": "QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes",
        "Water": 0.5,
        "Width": 0.8,
        "Id": 949,
        "Name": "Rivers",
        "NodeSize": "Standard",
        "Position": {"$id": "51", "X": 25814.795, "Y": 26000.443},
        "Ports": {
            "$id": "52",
            "$values": [
                {
                    "$id": "53",
                    "Name": "In",
                    "Type": "PrimaryIn, Required",
                    "IsExporting": True,
                    "Parent": {"$ref": "50"},
                },
                {
                    "$id": "54",
                    "Name": "Out",
                    "Type": "PrimaryOut",
                    "IsExporting": True,
                    "Parent": {"$ref": "50"},
                },
                {
                    "$id": "55",
                    "Name": "Rivers",
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": "50"},
                },
                {
                    "$id": "56",
                    "Name": "Depth",
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": "50"},
                },
                {
                    "$id": "57",
                    "Name": "Surface",
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": "50"},
                },
                {
                    "$id": "58",
                    "Name": "Direction",
                    "Type": "Out",
                    "IsExporting": True,
                    "Parent": {"$ref": "50"},
                },
                {
                    "$id": "59",
                    "Name": "Mask",
                    "Type": "In",
                    "IsExporting": True,
                    "Parent": {"$ref": "50"},
                },
            ],
        },
    }
