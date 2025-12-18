"""Tests for YAML-based template system.

These tests verify that the new YAML template loader works correctly
and maintains compatibility with the legacy Python templates.
"""

import pytest

from mcp_gaea2.templates import (
    create_workflow_from_template_yaml,
    get_all_templates,
    get_legacy_workflow_templates,
    get_template,
    get_template_categories,
    get_template_metadata,
    get_template_names,
    get_templates_by_category,
    get_templates_by_difficulty,
    instantiate_template,
    list_templates,
)


class TestTemplateLoading:
    """Test YAML template file loading."""

    def test_template_names_loads(self):
        """Test that template names can be loaded from YAML."""
        names = get_template_names()
        assert isinstance(names, set)
        assert len(names) >= 11  # We have 11 templates

    def test_all_expected_templates_exist(self):
        """Test that all expected templates exist."""
        names = get_template_names()

        expected = [
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

        for template in expected:
            assert template in names, f"Missing template: {template}"

    def test_template_categories_loads(self):
        """Test that template categories can be loaded."""
        categories = get_template_categories()
        assert isinstance(categories, dict)

        # Check expected categories exist
        expected_cats = ["general", "mountain", "volcanic", "canyon", "coastal", "arctic", "river"]
        for cat in expected_cats:
            assert cat in categories, f"Missing category: {cat}"

    def test_all_templates_loads(self):
        """Test that all templates can be loaded."""
        templates = get_all_templates()
        assert isinstance(templates, dict)
        assert len(templates) >= 11


class TestTemplateDefinitions:
    """Test individual template definitions."""

    def test_basic_terrain_template(self):
        """Test basic_terrain template definition."""
        template = get_template("basic_terrain")
        assert template is not None

        # Check metadata
        assert template.get("category") == "general"
        assert template.get("difficulty") == "beginner"

        # Check nodes exist
        nodes = template.get("nodes", [])
        assert len(nodes) >= 4

        # Check for expected node types
        node_types = [n["type"] for n in nodes]
        assert "Mountain" in node_types
        assert "Erosion2" in node_types
        assert "Export" in node_types

    def test_volcanic_terrain_template(self):
        """Test volcanic_terrain template definition."""
        template = get_template("volcanic_terrain")
        assert template is not None

        nodes = template.get("nodes", [])
        node_types = [n["type"] for n in nodes]
        assert "Volcano" in node_types
        assert "Thermal" in node_types

    def test_mountain_range_template(self):
        """Test mountain_range template definition."""
        template = get_template("mountain_range")
        assert template is not None

        nodes = template.get("nodes", [])
        node_types = [n["type"] for n in nodes]
        assert "Mountain" in node_types
        assert "Ridge" in node_types
        assert "Snow" in node_types

    def test_unknown_template_returns_none(self):
        """Test that unknown template returns None."""
        unknown = get_template("NonExistentTemplate")
        assert unknown is None


class TestTemplateMetadata:
    """Test template metadata functions."""

    def test_get_metadata(self):
        """Test getting template metadata."""
        metadata = get_template_metadata("basic_terrain")
        assert metadata is not None

        assert metadata["name"] == "basic_terrain"
        assert "description" in metadata
        assert metadata["category"] == "general"
        assert metadata["difficulty"] == "beginner"
        assert metadata["node_count"] >= 4

    def test_metadata_for_unknown_template(self):
        """Test metadata for unknown template returns None."""
        metadata = get_template_metadata("NonExistent")
        assert metadata is None


class TestTemplateFiltering:
    """Test template filtering functions."""

    def test_templates_by_category(self):
        """Test getting templates by category."""
        mountain_templates = get_templates_by_category("mountain")
        assert isinstance(mountain_templates, list)
        assert "detailed_mountain" in mountain_templates
        assert "mountain_range" in mountain_templates

    def test_templates_by_difficulty(self):
        """Test getting templates by difficulty."""
        beginner_templates = get_templates_by_difficulty("beginner")
        assert "basic_terrain" in beginner_templates

        advanced_templates = get_templates_by_difficulty("advanced")
        assert "volcanic_island" in advanced_templates

    def test_list_templates_no_filter(self):
        """Test listing templates without filter."""
        templates = list_templates()
        assert len(templates) >= 11

        # Check structure
        for t in templates:
            assert "name" in t
            assert "description" in t
            assert "category" in t
            assert "difficulty" in t
            assert "node_count" in t

    def test_list_templates_with_category(self):
        """Test listing templates with category filter."""
        templates = list_templates(category="volcanic")
        assert len(templates) >= 2
        for t in templates:
            assert t["category"] == "volcanic"

    def test_list_templates_with_difficulty(self):
        """Test listing templates with difficulty filter."""
        templates = list_templates(difficulty="intermediate")
        assert len(templates) >= 4
        for t in templates:
            assert t["difficulty"] == "intermediate"


class TestTemplateInstantiation:
    """Test template instantiation functions."""

    def test_instantiate_basic_template(self):
        """Test instantiating a basic template."""
        nodes = instantiate_template("basic_terrain")
        assert isinstance(nodes, list)
        assert len(nodes) >= 4

        # Check nodes have required fields
        for node in nodes:
            assert "type" in node
            assert "name" in node

    def test_instantiate_with_customizations(self):
        """Test instantiating with customizations."""
        customizations = {"BaseTerrain": {"Scale": 2.0, "Height": 0.9}}
        nodes = instantiate_template("basic_terrain", customizations)

        # Find the BaseTerrain node
        base_terrain = None
        for node in nodes:
            if node["name"] == "BaseTerrain":
                base_terrain = node
                break

        assert base_terrain is not None
        assert base_terrain["properties"]["Scale"] == 2.0
        assert base_terrain["properties"]["Height"] == 0.9

    def test_customizations_dont_modify_original(self):
        """Test that customizations don't modify the cached template."""
        # First instantiation with customization
        customizations = {"BaseTerrain": {"Scale": 999.0}}
        instantiate_template("basic_terrain", customizations)

        # Second instantiation without customization
        nodes = instantiate_template("basic_terrain")

        # Should have original value
        base_terrain = None
        for node in nodes:
            if node["name"] == "BaseTerrain":
                base_terrain = node
                break

        assert base_terrain["properties"]["Scale"] == 1.0  # Original value

    def test_instantiate_unknown_template_raises(self):
        """Test that instantiating unknown template raises ValueError."""
        with pytest.raises(ValueError, match="Template not found"):
            instantiate_template("NonExistentTemplate")


class TestLegacyCompatibility:
    """Test backward compatibility with legacy template format."""

    def test_legacy_workflow_templates(self):
        """Test legacy WORKFLOW_TEMPLATES adapter."""
        legacy = get_legacy_workflow_templates()
        assert isinstance(legacy, dict)

        # Check expected templates exist
        assert "basic_terrain" in legacy
        assert "volcanic_terrain" in legacy
        assert "mountain_range" in legacy

        # Check format - should be list of nodes
        basic = legacy["basic_terrain"]
        assert isinstance(basic, list)
        assert len(basic) >= 4

        # Check node structure
        for node in basic:
            assert "type" in node
            assert "name" in node

    def test_legacy_template_has_save_definition(self):
        """Test that legacy templates preserve save_definition."""
        legacy = get_legacy_workflow_templates()
        basic = legacy["basic_terrain"]

        # Find Export node
        export_node = None
        for node in basic:
            if node["type"] == "Export":
                export_node = node
                break

        assert export_node is not None
        assert "save_definition" in export_node
        save_def = export_node["save_definition"]
        assert save_def["filename"] == "heightmap"
        assert save_def["format"] == "PNG16"
        assert save_def["enabled"] is True

    def test_create_workflow_from_template(self):
        """Test creating workflow from template."""
        workflow = create_workflow_from_template_yaml("basic_terrain", project_name="test_project", output_directory="/output")

        assert workflow["name"] == "test_project"
        assert "nodes" in workflow
        assert "connections" in workflow
        assert workflow["version"] == "2.2.6.0"

    def test_create_workflow_updates_export_path(self):
        """Test that workflow creation updates export paths."""
        workflow = create_workflow_from_template_yaml("basic_terrain", output_directory="/custom/output")

        # Find Export node
        export_node = None
        for node in workflow["nodes"]:
            if node["type"] == "Export":
                export_node = node
                break

        assert export_node is not None
        assert "/custom/output" in export_node["save_definition"]["filename"]


class TestTemplateNodeProperties:
    """Test that template nodes have proper properties."""

    def test_mountain_node_properties(self):
        """Test Mountain node has expected properties."""
        nodes = instantiate_template("basic_terrain")

        mountain = None
        for node in nodes:
            if node["type"] == "Mountain":
                mountain = node
                break

        assert mountain is not None
        props = mountain.get("properties", {})
        assert "Scale" in props
        assert "Height" in props
        assert "Style" in props

    def test_erosion2_node_properties(self):
        """Test Erosion2 node has expected properties."""
        nodes = instantiate_template("basic_terrain")

        erosion = None
        for node in nodes:
            if node["type"] == "Erosion2":
                erosion = node
                break

        assert erosion is not None
        props = erosion.get("properties", {})
        assert "Duration" in props
        assert "Downcutting" in props
        assert "ErosionScale" in props
        assert "Seed" in props

    def test_volcano_node_position_properties(self):
        """Test Volcano node has position properties."""
        nodes = instantiate_template("volcanic_terrain")

        volcano = None
        for node in nodes:
            if node["type"] == "Volcano":
                volcano = node
                break

        assert volcano is not None
        props = volcano.get("properties", {})
        assert "X" in props
        assert "Y" in props
        # Verify these are reasonable position values
        assert 0 <= props["X"] <= 1
        assert 0 <= props["Y"] <= 1
