"""Tests for YAML-based schema system.

These tests verify that the new YAML schema loader works correctly
and maintains compatibility with the legacy Python schema.
"""

from mcp_gaea2.schema.schema_loader import (
    get_all_node_definitions,
    get_common_properties,
    get_legacy_property_definitions,
    get_legacy_valid_node_types,
    get_node_categories,
    get_node_category,
    get_node_definition,
    get_node_ports,
    get_node_properties,
    get_port_types,
    get_valid_node_types,
    is_port_compatible,
    validate_property_value,
)


class TestYAMLSchemaLoading:
    """Test YAML schema file loading."""

    def test_valid_node_types_loads(self):
        """Test that valid node types can be loaded from YAML."""
        node_types = get_valid_node_types()
        assert isinstance(node_types, set)
        assert len(node_types) > 50  # Should have many node types

    def test_core_nodes_exist(self):
        """Test that core node types exist in schema."""
        node_types = get_valid_node_types()

        # Essential terrain nodes
        assert "Mountain" in node_types
        assert "Volcano" in node_types
        assert "Island" in node_types
        assert "Canyon" in node_types

        # Essential simulation nodes
        assert "Erosion2" in node_types
        assert "Rivers" in node_types
        assert "Snow" in node_types
        assert "Thermal" in node_types

        # Essential utility nodes
        assert "Combine" in node_types
        assert "Export" in node_types

    def test_node_categories_loads(self):
        """Test that node categories can be loaded."""
        categories = get_node_categories()
        assert isinstance(categories, dict)

        # Check expected categories exist
        expected_cats = ["primitive", "terrain", "modify", "simulate", "output", "utility"]
        for cat in expected_cats:
            assert cat in categories, f"Missing category: {cat}"

    def test_all_node_definitions_loads(self):
        """Test that all node definitions can be loaded."""
        definitions = get_all_node_definitions()
        assert isinstance(definitions, dict)
        assert len(definitions) > 0


class TestNodeDefinitions:
    """Test individual node definitions."""

    def test_mountain_definition(self):
        """Test Mountain node definition."""
        mountain = get_node_definition("Mountain")
        assert mountain is not None

        # Check category
        assert mountain.get("category") == "terrain"

        # Check properties exist
        props = mountain.get("properties", {})
        assert "Scale" in props
        assert "Height" in props
        assert "Style" in props
        assert "Seed" in props

    def test_erosion2_definition(self):
        """Test Erosion2 node definition."""
        erosion = get_node_definition("Erosion2")
        assert erosion is not None

        props = erosion.get("properties", {})
        assert "Duration" in props
        assert "Downcutting" in props
        assert "ErosionScale" in props

    def test_combine_definition(self):
        """Test Combine node definition."""
        combine = get_node_definition("Combine")
        assert combine is not None

        props = combine.get("properties", {})
        assert "Mode" in props
        assert "Ratio" in props

        # Check Mode has options
        mode_prop = props["Mode"]
        assert mode_prop.get("type") == "enum"
        assert "Blend" in mode_prop.get("options", [])

    def test_unknown_node_returns_none(self):
        """Test that unknown node returns None."""
        unknown = get_node_definition("NonExistentNode")
        assert unknown is None


class TestNodeProperties:
    """Test node property access."""

    def test_get_mountain_properties(self):
        """Test getting Mountain properties."""
        props = get_node_properties("Mountain")
        assert isinstance(props, dict)
        assert "Scale" in props
        assert "Height" in props

    def test_property_has_type(self):
        """Test that properties have type definitions."""
        props = get_node_properties("Mountain")
        for prop_name, prop_def in props.items():
            assert "type" in prop_def, f"Property {prop_name} missing type"

    def test_property_has_default(self):
        """Test that properties have default values."""
        props = get_node_properties("Mountain")
        for prop_name, prop_def in props.items():
            assert "default" in prop_def, f"Property {prop_name} missing default"

    def test_numeric_property_has_range(self):
        """Test that numeric properties have ranges."""
        props = get_node_properties("Mountain")
        for prop_name, prop_def in props.items():
            if prop_def.get("type") in ("int", "float"):
                assert "range" in prop_def, f"Numeric property {prop_name} missing range"

    def test_enum_property_has_options(self):
        """Test that enum properties have options."""
        props = get_node_properties("Mountain")
        style_prop = props.get("Style", {})
        assert style_prop.get("type") == "enum"
        assert "options" in style_prop
        assert len(style_prop["options"]) > 0


class TestNodePorts:
    """Test node port definitions."""

    def test_mountain_ports(self):
        """Test Mountain node ports (generator - no inputs)."""
        ports = get_node_ports("Mountain")
        assert "inputs" in ports
        assert "outputs" in ports
        assert len(ports["inputs"]) == 0  # Generator node
        assert len(ports["outputs"]) > 0

    def test_erosion2_ports(self):
        """Test Erosion2 node ports (multi-output)."""
        ports = get_node_ports("Erosion2")
        assert len(ports["inputs"]) >= 1
        assert len(ports["outputs"]) >= 3  # Out, Flow, Wear, Deposits

    def test_rivers_ports(self):
        """Test Rivers node ports (multi-output)."""
        ports = get_node_ports("Rivers")
        assert len(ports["outputs"]) >= 4  # Out, Rivers, Flow, Depth, Wear

    def test_combine_ports(self):
        """Test Combine node ports (dual input)."""
        ports = get_node_ports("Combine")
        assert len(ports["inputs"]) >= 2  # In, Input2, optionally Mask

    def test_export_ports(self):
        """Test Export node ports (no outputs)."""
        ports = get_node_ports("Export")
        assert len(ports["inputs"]) >= 1
        assert len(ports["outputs"]) == 0


class TestNodeCategories:
    """Test node category functions."""

    def test_get_mountain_category(self):
        """Test getting Mountain category."""
        category = get_node_category("Mountain")
        assert category == "terrain"

    def test_get_erosion2_category(self):
        """Test getting Erosion2 category."""
        category = get_node_category("Erosion2")
        assert category == "simulate"

    def test_get_combine_category(self):
        """Test getting Combine category."""
        category = get_node_category("Combine")
        assert category == "utility"

    def test_get_export_category(self):
        """Test getting Export category."""
        category = get_node_category("Export")
        assert category == "output"


class TestPortCompatibility:
    """Test port type compatibility."""

    def test_heightfield_to_heightfield(self):
        """Test heightfield to heightfield connection."""
        assert is_port_compatible("heightfield", "heightfield") is True

    def test_heightfield_to_mask(self):
        """Test heightfield to mask connection."""
        assert is_port_compatible("heightfield", "mask") is True

    def test_mask_to_heightfield(self):
        """Test mask to heightfield connection."""
        assert is_port_compatible("mask", "heightfield") is True

    def test_color_to_color(self):
        """Test color to color connection."""
        assert is_port_compatible("color", "color") is True


class TestPropertyValidation:
    """Test property value validation."""

    def test_valid_float_value(self):
        """Test valid float property value."""
        is_valid, error, fix = validate_property_value("Mountain", "Scale", 2.0)
        assert is_valid is True
        assert error is None

    def test_invalid_float_below_range(self):
        """Test float value below minimum."""
        is_valid, error, fix = validate_property_value("Mountain", "Scale", 0.01)
        assert is_valid is False
        assert "below minimum" in error.lower()
        assert fix == 0.1  # Should suggest minimum

    def test_invalid_float_above_range(self):
        """Test float value above maximum."""
        is_valid, error, fix = validate_property_value("Mountain", "Scale", 100.0)
        assert is_valid is False
        assert "above maximum" in error.lower()
        assert fix == 5.0  # Should suggest maximum

    def test_valid_enum_value(self):
        """Test valid enum property value."""
        is_valid, error, fix = validate_property_value("Mountain", "Style", "Alpine")
        assert is_valid is True

    def test_invalid_enum_value(self):
        """Test invalid enum property value."""
        is_valid, error, fix = validate_property_value("Mountain", "Style", "Invalid")
        assert is_valid is False
        assert "invalid enum" in error.lower()

    def test_valid_int_value(self):
        """Test valid int property value."""
        is_valid, error, fix = validate_property_value("Mountain", "Seed", 12345)
        assert is_valid is True

    def test_valid_bool_value(self):
        """Test valid bool property value."""
        is_valid, error, fix = validate_property_value("Mountain", "ReduceDetails", True)
        assert is_valid is True


class TestLegacyCompatibility:
    """Test backward compatibility with legacy schema."""

    def test_legacy_node_types_match(self):
        """Test that YAML node types include all legacy types."""
        yaml_types = get_valid_node_types()
        legacy_types = get_legacy_valid_node_types()

        # YAML types should be a superset of legacy types
        # (or at least include the commonly used ones)
        common_types = ["Mountain", "Erosion2", "Rivers", "Combine", "Export", "SatMap"]
        for node_type in common_types:
            assert node_type in yaml_types
            assert node_type in legacy_types

    def test_legacy_property_format(self):
        """Test that legacy adapter returns correct format."""
        legacy_props = get_legacy_property_definitions()
        assert isinstance(legacy_props, dict)

        # Check Mountain properties are in legacy format
        if "Mountain" in legacy_props:
            mountain_props = legacy_props["Mountain"]
            assert isinstance(mountain_props, dict)

            # Legacy format uses {min, max} dict for ranges
            for prop_name, prop_def in mountain_props.items():
                if "range" in prop_def:
                    assert isinstance(prop_def["range"], dict)
                    assert "min" in prop_def["range"]
                    assert "max" in prop_def["range"]


class TestCommonProperties:
    """Test common property definitions."""

    def test_common_properties_exist(self):
        """Test that common properties are defined."""
        common = get_common_properties()
        assert isinstance(common, dict)

        # Check common properties
        expected = ["Seed", "Scale", "Height", "Strength", "X", "Y"]
        for prop in expected:
            assert prop in common, f"Missing common property: {prop}"

    def test_seed_property_definition(self):
        """Test Seed common property definition."""
        common = get_common_properties()
        seed = common.get("Seed", {})

        assert seed.get("type") == "int"
        assert seed.get("default") == 0
        assert seed.get("range") == [0, 999999]


class TestPortTypes:
    """Test port type definitions."""

    def test_port_types_exist(self):
        """Test that port types are defined."""
        port_types = get_port_types()
        assert isinstance(port_types, dict)

        # Check essential port types
        expected = ["heightfield", "mask", "color"]
        for pt in expected:
            assert pt in port_types, f"Missing port type: {pt}"

    def test_heightfield_port_type(self):
        """Test heightfield port type definition."""
        port_types = get_port_types()
        hf = port_types.get("heightfield", {})

        assert "description" in hf
        assert "compatible_with" in hf
        assert "mask" in hf["compatible_with"]
