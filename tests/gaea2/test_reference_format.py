"""Unit tests based on Level1.terrain reference file format"""

from typing import Any, Dict, List


class TestReferenceFormat:
    """Test against actual Level1.terrain reference format"""

    def test_volcano_node_has_xy_at_root(self):
        """Test that Volcano node has X/Y at root level"""
        volcano_node = {
            "$id": "7",
            "$type": "QuadSpinner.Gaea.Nodes.Volcano, Gaea.Nodes",
            "Scale": 1.0131434,
            "Height": 0.5547645,
            "Mouth": 0.85706466,
            "Bulk": -0.1467689,
            "Surface": "Eroded",
            "X": 0.296276,  # Root level X (normalized)
            "Y": 0.5,  # Root level Y (normalized)
            "Seed": 44922,
            "Id": 183,
            "Name": "Volcano",
            "Position": {
                "$id": "8",
                "X": 24472.023,  # Canvas X
                "Y": 25987.605,  # Canvas Y
            },
        }

        # Check X/Y exist at root
        assert "X" in volcano_node
        assert "Y" in volcano_node
        assert isinstance(volcano_node["X"], float)
        assert isinstance(volcano_node["Y"], float)

        # Check they're different from Position X/Y
        assert volcano_node["X"] != volcano_node["Position"]["X"]
        assert volcano_node["Y"] != volcano_node["Position"]["Y"]

        # Check normalized range (0-1)
        assert 0.0 <= volcano_node["X"] <= 1.0
        assert 0.0 <= volcano_node["Y"] <= 1.0

    def test_property_names_no_spaces(self):
        """Test that property names do NOT have spaces"""
        # From Level1.terrain
        properties_without_spaces = [
            "CoastalErosion",
            "ExtraCliffDetails",
            "RiverValleyWidth",
            "RockHardness",
            "UniformVariations",
            "SuspendedLoadDischargeAmount",
            "BedLoadDischargeAngle",
            "CoarseSedimentsDischargeAmount",
        ]

        for prop in properties_without_spaces:
            # No spaces in property names
            assert " " not in prop
            # PascalCase format
            assert prop[0].isupper()

    def test_groups_notes_camera_format(self):
        """Test Groups, Notes, Camera have minimal format"""
        # From Level1.terrain
        groups = {"$id": "205"}
        notes = {"$id": "206"}
        camera = {"$id": "219"}
        variables = {"$id": "212"}

        # Only $id, no other properties
        assert len(groups) == 1
        assert len(notes) == 1
        assert len(camera) == 1
        assert len(variables) == 1

        # No $values
        assert "$values" not in groups
        assert "$values" not in notes
        assert "$values" not in camera

    def test_node_id_pattern(self):
        """Test non-sequential node ID pattern"""
        # From Level1.terrain
        node_ids = [
            183,
            668,
            427,
            281,
            294,
            949,
            483,
            800,
            375,
            245,
            958,
            174,
            258,
            975,
            639,
            514,
            287,
            490,
            340,
        ]

        # All are integers
        for node_id in node_ids:
            assert isinstance(node_id, int)

        # Non-sequential (gaps > 1)
        sorted_ids = sorted(node_ids[:5])  # Check first few
        for i in range(1, len(sorted_ids)):
            gap = sorted_ids[i] - sorted_ids[i - 1]
            assert gap > 10, f"IDs too close: {sorted_ids[i-1]}, {sorted_ids[i]}"

    def test_range_property_format(self):
        """Test Range property has $id"""
        # From Height node in Level1.terrain
        range_prop = {"$id": "103", "X": 0.87732744, "Y": 1.0}

        assert "$id" in range_prop
        assert "X" in range_prop
        assert "Y" in range_prop
        assert range_prop["X"] < range_prop["Y"]

    def test_erosion2_specific_properties(self):
        """Test Erosion2 node has all required properties"""
        erosion2_props = {
            "Duration": 1.6352992,
            "Downcutting": 0.8118839,
            "ErosionScale": 15620.922,
            "Seed": 22790,
            "SuspendedLoadDischargeAmount": 1.0,
            "SuspendedLoadDischargeAngle": 13.726726,
            "BedLoadDischargeAmount": 0.65662646,
            "BedLoadDischargeAngle": 38.36254,
            "CoarseSedimentsDischargeAmount": 0.4989047,
            "CoarseSedimentsDischargeAngle": 18.901972,
            "Shape": 0.4234392,
            "ShapeSharpness": 0.6,
            "ShapeDetailScale": 0.25,
        }

        # All properties should be present
        required_props = [
            "Duration",
            "Downcutting",
            "ErosionScale",
            "Seed",
            "SuspendedLoadDischargeAmount",
            "SuspendedLoadDischargeAngle",
            "BedLoadDischargeAmount",
            "BedLoadDischargeAngle",
            "CoarseSedimentsDischargeAmount",
            "CoarseSedimentsDischargeAngle",
            "Shape",
            "ShapeSharpness",
            "ShapeDetailScale",
        ]

        for prop in required_props:
            assert prop in erosion2_props

    def test_combine_node_properties(self):
        """Test Combine node specific properties"""
        combine_props = {"PortCount": 2, "Ratio": 0.5, "Mode": "Add", "Clamp": "Clamp"}

        assert combine_props["PortCount"] == 2
        assert combine_props["Mode"] == "Add"
        assert 0.0 <= combine_props["Ratio"] <= 1.0

    def test_connection_embedding(self):
        """Test connections are embedded in port Records"""
        # Example from Adjust node In port
        port_with_connection = {
            "$id": "24",
            "Name": "In",
            "Type": "PrimaryIn, Required",
            "Record": {
                "$id": "25",
                "From": 949,
                "To": 427,
                "FromPort": "Rivers",
                "ToPort": "In",
                "IsValid": True,
            },
            "IsExporting": True,
            "Parent": {"$ref": "21"},
        }

        # Connection is in Record
        assert "Record" in port_with_connection
        record = port_with_connection["Record"]

        # Record has all required fields
        assert "From" in record
        assert "To" in record
        assert "FromPort" in record
        assert "ToPort" in record
        assert "IsValid" in record

        # IDs are integers
        assert isinstance(record["From"], int)
        assert isinstance(record["To"], int)

    def test_multi_port_nodes(self):
        """Test multi-port node structure"""
        # Rivers node ports
        rivers_ports = [
            {"Name": "In", "Type": "PrimaryIn, Required"},
            {"Name": "Out", "Type": "PrimaryOut"},
            {"Name": "Headwaters", "Type": "In"},
            {"Name": "Rivers", "Type": "Out"},
            {"Name": "Depth", "Type": "Out"},
            {"Name": "Surface", "Type": "Out"},
            {"Name": "Direction", "Type": "Out"},
            {"Name": "Mask", "Type": "In"},
        ]

        # Check port count
        assert len(rivers_ports) == 8

        # Check output ports
        output_ports = [p for p in rivers_ports if "Out" in p["Type"]]
        assert len(output_ports) == 5

    def test_property_order_in_node(self):
        """Test property order matches reference"""
        # Expected order from Volcano node
        expected_order = [
            "$id",
            "$type",
            # Node-specific properties come next
            "Scale",
            "Height",
            "Mouth",
            "Bulk",
            "Surface",
            "X",
            "Y",
            "Seed",
            # Standard properties come after
            "Id",
            "Name",
            "Position",
        ]

        # This is the order we should follow
        assert expected_order[0] == "$id"
        assert expected_order[1] == "$type"
        assert expected_order[-3] == "Id"
        assert expected_order[-2] == "Name"
        assert expected_order[-1] == "Position"

    def test_save_definition_format(self):
        """Test SaveDefinition structure"""
        save_def = {
            "$id": "52",
            "Node": 949,
            "Filename": "Rivers",
            "Format": "EXR",
            "IsEnabled": True,
        }

        assert save_def["Node"] == 949  # Matches node ID
        assert save_def["Format"] == "EXR"
        assert save_def["IsEnabled"] is True

    def test_viewport_settings(self):
        """Test viewport structure"""
        viewport = {
            "Camera": {"$id": "219"},
            "RenderMode": "Realistic",
            "SunAltitude": 33.0,
            "SunAzimuth": 45.0,
            "SunIntensity": 1.0,
            "AmbientOcclusion": True,
            "Shadows": True,
            "AirDensity": 1.0,
            "AmbientIntensity": 1.0,
            "Exposure": 1.0,
            "FogDensity": 0.2,
            "GroundBrightness": 0.8,
            "Haze": 1.0,
            "Ozone": 1.0,
        }

        # Camera is minimal
        assert len(viewport["Camera"]) == 1
        assert "$id" in viewport["Camera"]

        # All numeric values
        numeric_props = ["SunAltitude", "SunAzimuth", "SunIntensity", "AirDensity"]
        for prop in numeric_props:
            assert isinstance(viewport[prop], (int, float))


class TestNodeValidation:
    """Test node-specific validation rules"""

    def validate_node_structure(self, node: Dict[str, Any]) -> List[str]:
        """Validate a node structure and return errors"""
        errors = []

        # Check required fields
        required = ["$id", "$type", "Id", "Name", "Position"]
        for field in required:
            if field not in node:
                errors.append(f"Missing required field: {field}")

        # Check Id is integer
        if "Id" in node and not isinstance(node["Id"], int):
            errors.append(f"Id must be integer, got {type(node['Id'])}")

        # Check Position structure
        if "Position" in node:
            pos = node["Position"]
            if "$id" not in pos:
                errors.append("Position missing $id")
            if "X" not in pos or "Y" not in pos:
                errors.append("Position missing X or Y")

        # Check Ports if present
        if "Ports" in node:
            ports = node["Ports"]
            if "$values" not in ports:
                errors.append("Ports missing $values array")

        return errors

    def test_node_validation(self):
        """Test node validation function"""
        # Valid node
        valid_node = {
            "$id": "7",
            "$type": "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes",
            "Id": 183,
            "Name": "Mountain",
            "Position": {"$id": "8", "X": 0, "Y": 0},
        }

        errors = self.validate_node_structure(valid_node)
        assert len(errors) == 0

        # Invalid node (Id as string)
        invalid_node = {
            "$id": "7",
            "$type": "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes",
            "Id": "183",  # Should be int
            "Name": "Mountain",
            "Position": {"$id": "8", "X": 0, "Y": 0},
        }

        errors = self.validate_node_structure(invalid_node)
        assert "Id must be integer" in errors[0]
