"""Tests for the unified CoreValidator.

These tests verify that the YAML schema-based CoreValidator works correctly
for workflow validation, property checking, and connection validation.
"""

from mcp_gaea2.validation import (
    CoreValidator,
    create_core_validator,
    validate_node_type,
    validate_properties,
    validate_workflow,
)


class TestCoreValidatorCreation:
    """Test CoreValidator instantiation."""

    def test_create_validator(self):
        """Test creating a CoreValidator."""
        validator = create_core_validator()
        assert isinstance(validator, CoreValidator)

    def test_validator_has_valid_node_types(self):
        """Test that validator has valid node types loaded."""
        validator = CoreValidator()
        assert len(validator.valid_node_types) > 50


class TestNodeTypeValidation:
    """Test node type validation."""

    def test_valid_node_type(self):
        """Test validation of valid node types."""
        assert validate_node_type("Mountain") is True
        assert validate_node_type("Erosion2") is True
        assert validate_node_type("Combine") is True
        assert validate_node_type("Export") is True

    def test_invalid_node_type(self):
        """Test validation of invalid node types."""
        assert validate_node_type("NonExistentNode") is False
        assert validate_node_type("InvalidType") is False
        assert validate_node_type("") is False

    def test_validate_nodes_in_workflow(self):
        """Test validating node types in a workflow."""
        validator = CoreValidator()
        nodes = [
            {"type": "Mountain", "id": "1"},
            {"type": "Erosion2", "id": "2"},
            {"type": "Export", "id": "3"},
        ]
        errors = validator.validate_node_types(nodes)
        assert len(errors) == 0

    def test_validate_invalid_nodes(self):
        """Test that invalid nodes produce errors."""
        validator = CoreValidator()
        nodes = [
            {"type": "Mountain", "id": "1"},
            {"type": "InvalidNode", "id": "2"},
        ]
        errors = validator.validate_node_types(nodes)
        assert len(errors) == 1
        assert "InvalidNode" in errors[0]


class TestPropertyValidation:
    """Test property validation."""

    def test_validate_valid_properties(self):
        """Test validation of valid properties."""
        is_valid, issues, fixed = validate_properties("Mountain", {"Scale": 1.0, "Height": 0.7})
        assert is_valid is True
        assert len(issues) == 0

    def test_validate_out_of_range_property(self):
        """Test that out-of-range values get fixed."""
        is_valid, issues, fixed = validate_properties(
            "Mountain",
            {"Scale": 100.0},  # Above max range
        )
        # Should auto-fix
        assert fixed["Scale"] == 5.0  # Max value from schema
        assert len(issues) > 0

    def test_validate_invalid_enum_property(self):
        """Test that invalid enum values get flagged."""
        is_valid, issues, fixed = validate_properties("Mountain", {"Style": "InvalidStyle"})
        assert len(issues) > 0
        assert "InvalidStyle" in str(issues)


class TestConnectionValidation:
    """Test connection validation."""

    def test_validate_valid_connection(self):
        """Test validation of valid connection."""
        validator = CoreValidator()
        nodes = [
            {"type": "Mountain", "id": "1"},
            {"type": "Erosion2", "id": "2"},
        ]
        node_map = {str(n["id"]): n for n in nodes}
        connection = {
            "source": "1",
            "target": "2",
            "source_port": "Out",
            "target_port": "In",
        }

        is_valid, error = validator.validate_connection(connection, node_map)
        assert is_valid is True
        assert error is None

    def test_validate_connection_missing_source(self):
        """Test connection with missing source node."""
        validator = CoreValidator()
        nodes = [
            {"type": "Erosion2", "id": "2"},
        ]
        node_map = {str(n["id"]): n for n in nodes}
        connection = {
            "source": "1",  # Doesn't exist
            "target": "2",
        }

        is_valid, error = validator.validate_connection(connection, node_map)
        assert is_valid is False
        assert "not found" in error

    def test_validate_all_connections(self):
        """Test validating all connections in a workflow."""
        validator = CoreValidator()
        nodes = [
            {"type": "Mountain", "id": "1"},
            {"type": "Erosion2", "id": "2"},
            {"type": "Export", "id": "3"},
        ]
        connections = [
            {"source": "1", "target": "2", "source_port": "Out", "target_port": "In"},
            {"source": "2", "target": "3", "source_port": "Out", "target_port": "In"},
        ]

        is_valid, errors, warnings = validator.validate_connections(nodes, connections)
        assert is_valid is True
        assert len(errors) == 0


class TestWorkflowValidation:
    """Test full workflow validation."""

    def test_validate_simple_workflow(self):
        """Test validating a simple valid workflow."""
        workflow = {
            "nodes": [
                {"type": "Mountain", "id": "1", "properties": {"Scale": 1.0}},
                {"type": "Erosion2", "id": "2", "properties": {"Duration": 0.07}},
                {"type": "Export", "id": "3", "properties": {}},
            ],
            "connections": [
                {"source": "1", "target": "2", "source_port": "Out", "target_port": "In"},
                {"source": "2", "target": "3", "source_port": "Out", "target_port": "In"},
            ],
        }

        result = validate_workflow(workflow)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_workflow_with_fixes(self):
        """Test that workflow validation applies fixes."""
        workflow = {
            "nodes": [
                {"type": "Mountain", "id": "1", "properties": {"Scale": 100.0}},  # Out of range
            ],
            "connections": [],
        }

        result = validate_workflow(workflow, auto_fix=True)
        assert result["valid"] is True
        assert result["fixed"] is True
        assert len(result["fixes_applied"]) > 0
        # Check the property was fixed
        fixed_scale = result["workflow"]["nodes"][0]["properties"]["Scale"]
        assert fixed_scale == 5.0  # Max value

    def test_validate_workflow_strict_mode(self):
        """Test strict mode fails on warnings."""
        workflow = {
            "nodes": [
                {"type": "Mountain", "id": "1", "properties": {"Scale": 100.0}},
            ],
            "connections": [],
        }

        result = validate_workflow(workflow, auto_fix=True, strict=True)
        # Strict mode treats warnings as errors
        assert result["valid"] is False

    def test_validate_workflow_missing_type(self):
        """Test workflow with node missing type."""
        workflow = {
            "nodes": [
                {"id": "1", "properties": {}},  # Missing type
            ],
            "connections": [],
        }

        result = validate_workflow(workflow)
        assert result["valid"] is False
        assert any("type" in e.lower() for e in result["errors"])


class TestNodeStructureValidation:
    """Test node structure validation."""

    def test_validate_structure_valid(self):
        """Test valid node structure."""
        validator = CoreValidator()
        nodes = [
            {"type": "Mountain", "id": "1"},
            {"type": "Erosion2", "id": "2"},
        ]
        errors = validator.validate_node_structure(nodes)
        assert len(errors) == 0

    def test_validate_structure_missing_type(self):
        """Test node missing type field."""
        validator = CoreValidator()
        nodes = [
            {"id": "1", "properties": {}},  # Missing type
        ]
        errors = validator.validate_node_structure(nodes)
        assert len(errors) == 1
        assert "type" in errors[0].lower()

    def test_validate_structure_missing_id(self):
        """Test node missing id field."""
        validator = CoreValidator()
        nodes = [
            {"type": "Mountain"},  # Missing id
        ]
        errors = validator.validate_node_structure(nodes)
        assert len(errors) == 1
        assert "id" in errors[0].lower() or "name" in errors[0].lower()

    def test_validate_structure_duplicate_ids(self):
        """Test duplicate node IDs."""
        validator = CoreValidator()
        nodes = [
            {"type": "Mountain", "id": "1"},
            {"type": "Erosion2", "id": "1"},  # Duplicate
        ]
        errors = validator.validate_node_structure(nodes)
        assert len(errors) == 1
        assert "duplicate" in errors[0].lower()


class TestPropertyLimitedNodes:
    """Test nodes with property count restrictions."""

    def test_snow_property_limit(self):
        """Test Snow node property limit."""
        validator = CoreValidator()

        # More than 3 properties
        properties = {
            "Duration": 0.5,
            "SnowLine": 0.7,
            "Melt": 0.2,
            "Coverage": 0.8,
            "ExtraProp": 1.0,
        }

        is_valid, errors, warnings, fixed = validator.validate_node_properties("Snow", properties, auto_fix=True)

        # Should have reduced properties
        assert len(fixed) <= 3

    def test_non_limited_node_allows_many_properties(self):
        """Test that non-limited nodes allow many properties."""
        validator = CoreValidator()

        properties = {
            "Scale": 1.0,
            "Height": 0.7,
            "Style": "Alpine",
            "Bulk": "Normal",
            "Seed": 12345,
        }

        is_valid, errors, warnings, fixed = validator.validate_node_properties("Mountain", properties, auto_fix=True)

        # Mountain is not limited, should keep all properties
        assert len(fixed) >= 5


class TestApplyDefaults:
    """Test applying default properties."""

    def test_apply_defaults_to_empty(self):
        """Test applying defaults to empty properties."""
        validator = CoreValidator()
        result = validator.apply_default_properties("Mountain", {})

        # Should have default properties applied
        assert "Scale" in result or "Height" in result

    def test_apply_defaults_preserves_existing(self):
        """Test that defaults don't override existing values."""
        validator = CoreValidator()
        result = validator.apply_default_properties("Mountain", {"Scale": 2.0})

        # Should preserve the custom Scale
        assert result["Scale"] == 2.0
