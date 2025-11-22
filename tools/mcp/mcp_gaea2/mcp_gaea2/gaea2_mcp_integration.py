"""Integration module for enhanced Gaea 2 MCP tools

This module shows how to integrate the enhanced tools into the existing MCP server
"""

from typing import Any, Dict, List

from .generation.gaea2_enhanced import EnhancedGaea2Tools
from .utils.gaea2_workflow_tools import Gaea2WorkflowTools


class Gaea2MCPIntegration:
    """Integration class for enhanced Gaea 2 MCP tools"""

    @staticmethod
    def get_enhanced_tool_definitions() -> List[Dict[str, Any]]:
        """Get tool definitions for MCP server registration"""

        return [
            # Enhanced project creation
            {
                "name": "create_advanced_gaea2_project",
                "description": (
                    "Create an advanced Gaea 2 project with full feature support "
                    "including modifiers, groups, and automation"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string"},
                        "nodes": {"type": "array"},
                        "connections": {"type": "array"},
                        "groups": {"type": "array"},
                        "variables": {"type": "object"},
                        "build_config": {"type": "object"},
                        "viewport_settings": {"type": "object"},
                        "output_path": {"type": "string"},
                    },
                    "required": ["project_name", "nodes"],
                },
                "handler": EnhancedGaea2Tools.create_advanced_gaea2_project,
            },
            # Special node creators
            {
                "name": "create_gaea2_draw_node",
                "description": "Create a Draw node with stroke data for manual terrain painting",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "integer"},
                        "position": {"type": "object"},
                        "stroke_points": {"type": "array"},
                        "brush_size": {"type": "number"},
                        "soften": {"type": "number"},
                    },
                    "required": ["node_id", "position", "stroke_points"],
                },
                "handler": EnhancedGaea2Tools.create_draw_node,
            },
            {
                "name": "create_gaea2_mixer_node",
                "description": "Create a Mixer node with multiple texture layers",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "integer"},
                        "position": {"type": "object"},
                        "layers": {"type": "array"},
                    },
                    "required": ["node_id", "position", "layers"],
                },
                "handler": EnhancedGaea2Tools.create_mixer_node,
            },
            {
                "name": "create_gaea2_export_node",
                "description": "Create an export node for saving terrain outputs",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "integer"},
                        "position": {"type": "object"},
                        "filename": {"type": "string"},
                        "format": {"type": "string"},
                        "node_type": {"type": "string"},
                    },
                    "required": ["node_id", "position", "filename"],
                },
                "handler": EnhancedGaea2Tools.create_export_node,
            },
            # Workflow analysis tools
            {
                "name": "analyze_gaea2_workflow",
                "description": "Analyze workflow patterns and provide optimization suggestions",
                "input_schema": {
                    "type": "object",
                    "properties": {"project_file": {"type": "string"}},
                    "required": ["project_file"],
                },
                "handler": Gaea2WorkflowTools.analyze_workflow_patterns,
            },
            {
                "name": "profile_gaea2_performance",
                "description": "Profile project performance and identify bottlenecks",
                "input_schema": {
                    "type": "object",
                    "properties": {"project_file": {"type": "string"}},
                    "required": ["project_file"],
                },
                "handler": Gaea2WorkflowTools.profile_project_performance,
            },
            {
                "name": "optimize_gaea2_build",
                "description": "Get optimized build settings for different use cases",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_file": {"type": "string"},
                        "target_use_case": {
                            "type": "string",
                            "enum": ["game", "film", "visualization", "prototype"],
                        },
                    },
                    "required": ["project_file", "target_use_case"],
                },
                "handler": Gaea2WorkflowTools.optimize_build_settings,
            },
            # Batch and preset tools
            {
                "name": "batch_process_gaea2",
                "description": "Process multiple Gaea projects with common settings",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_files": {"type": "array"},
                        "common_settings": {"type": "object"},
                        "output_directory": {"type": "string"},
                    },
                    "required": ["project_files", "common_settings"],
                },
                "handler": Gaea2WorkflowTools.batch_process_projects,
            },
            {
                "name": "export_gaea2_preset",
                "description": "Export nodes as a reusable preset",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "nodes": {"type": "array"},
                        "connections": {"type": "array"},
                        "preset_name": {"type": "string"},
                        "category": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["nodes", "connections", "preset_name"],
                },
                "handler": Gaea2WorkflowTools.export_node_preset,
            },
            {
                "name": "import_gaea2_preset",
                "description": "Import a node preset into the project",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "preset_name": {"type": "string"},
                        "position": {"type": "object"},
                        "id_offset": {"type": "integer"},
                    },
                    "required": ["preset_name", "position"],
                },
                "handler": Gaea2WorkflowTools.import_node_preset,
            },
            {
                "name": "compare_gaea2_projects",
                "description": "Compare two Gaea projects and identify differences",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_a": {"type": "string"},
                        "project_b": {"type": "string"},
                    },
                    "required": ["project_a", "project_b"],
                },
                "handler": Gaea2WorkflowTools.compare_projects,
            },
        ]

    @staticmethod
    async def integrate_with_mcp_server(mcp_server_instance):
        """
        Example of how to integrate enhanced tools with existing MCP server

        This would be called in the MCP server's initialization
        """

        # Get enhanced tool definitions
        enhanced_tools = Gaea2MCPIntegration.get_enhanced_tool_definitions()

        # Register each tool with the MCP server
        for tool_def in enhanced_tools:
            # Assuming the MCP server has a register_tool method
            await mcp_server_instance.register_tool(
                name=tool_def["name"],
                description=tool_def["description"],
                input_schema=tool_def["input_schema"],
                handler=tool_def["handler"],
            )

        # Log successful integration
        print(f"Successfully integrated {len(enhanced_tools)} enhanced Gaea 2 tools")

    @staticmethod
    def get_tool_categories() -> Dict[str, List[str]]:
        """Get tools organized by category for documentation"""

        return {
            "Project Creation": [
                "create_advanced_gaea2_project",
                "create_gaea2_draw_node",
                "create_gaea2_mixer_node",
                "create_gaea2_export_node",
            ],
            "Analysis & Optimization": [
                "analyze_gaea2_workflow",
                "profile_gaea2_performance",
                "optimize_gaea2_build",
            ],
            "Workflow Management": [
                "batch_process_gaea2",
                "export_gaea2_preset",
                "import_gaea2_preset",
                "compare_gaea2_projects",
            ],
        }

    @staticmethod
    def get_example_usage() -> Dict[str, str]:
        """Get example usage for each tool category"""

        return {
            "create_advanced_project": """
# Create a complex terrain with erosion and texturing
await mcp.create_advanced_gaea2_project(
    project_name="Mountain Valley",
    nodes=[
        {"id": 100, "type": "Mountain", "modifiers": [...]},
        {"id": 101, "type": "Erosion2", "properties": {...}}
    ],
    connections=[{"from_node": 100, "to_node": 101}],
    groups=[{"name": "Terrain Base", "children": [100, 101]}],
    variables={"erosion_strength": {"Value": 50, "Type": "Float"}}
)
""",
            "analyze_workflow": """
# Analyze an existing project for optimization opportunities
result = await mcp.analyze_gaea2_workflow(
    project_file="my_terrain.terrain"
)
print(f"Complexity: {result['analysis']['complexity_level']}")
print(f"Suggestions: {result['suggestions']}")
""",
            "batch_processing": """
# Apply common settings to multiple projects
await mcp.batch_process_gaea2(
    project_files=["terrain1.terrain", "terrain2.terrain"],
    common_settings={
        "resolution": 4096,
        "export_formats": {"heightmap": "EXR", "textures": "PNG"}
    },
    output_directory="batch_output/"
)
""",
            "preset_management": """
# Export a node group as preset
await mcp.export_gaea2_preset(
    nodes=[erosion_node, deposits_node],
    connections=[...],
    preset_name="Advanced Erosion",
    category="erosion"
)

# Import preset into another project
result = await mcp.import_gaea2_preset(
    preset_name="Advanced Erosion",
    position={"x": 27000, "y": 26000}
)
""",
        }
