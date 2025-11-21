"""Scene management tools for Blender MCP Server."""

import uuid
from typing import Any, Dict


class SceneTools:
    """Scene analysis and optimization tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get scene management tool definitions."""
        return [
            {
                "name": "analyze_scene",
                "description": "Analyze scene statistics and performance metrics",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "analysis_type": {
                            "type": "string",
                            "enum": ["BASIC", "DETAILED", "PERFORMANCE", "MEMORY"],
                            "default": "BASIC",
                            "description": "Type of analysis to perform",
                        },
                    },
                    "required": ["project"],
                },
            },
            {
                "name": "optimize_scene",
                "description": "Optimize scene for better performance",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "optimization_type": {
                            "type": "string",
                            "enum": [
                                "MESH_CLEANUP",
                                "TEXTURE_OPTIMIZATION",
                                "MODIFIER_APPLY",
                                "INSTANCE_OPTIMIZATION",
                                "MATERIAL_CLEANUP",
                            ],
                            "default": "MESH_CLEANUP",
                            "description": "Type of optimization",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "target_polycount": {
                                    "type": "integer",
                                    "description": "Target polygon count for decimation",
                                },
                                "texture_size_limit": {
                                    "type": "integer",
                                    "default": 2048,
                                    "description": "Maximum texture size in pixels",
                                },
                                "remove_unused": {
                                    "type": "boolean",
                                    "default": True,
                                    "description": "Remove unused data blocks",
                                },
                            },
                        },
                    },
                    "required": ["project"],
                },
            },
        ]

    @staticmethod
    async def analyze_scene(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze scene statistics and performance."""
        project = str(server._validate_project_path(args["project"]))
        analysis_type = args.get("analysis_type", "BASIC")

        script_args = {
            "operation": "analyze_scene",
            "project": project,
            "analysis_type": analysis_type,
        }

        job_id = str(uuid.uuid4())
        result = await server.blender_executor.execute_script("scene.py", script_args, job_id)

        return {
            "success": True,
            "analysis_type": analysis_type,
            "statistics": result.get("statistics", {}),
            "message": "Scene analysis complete",
        }

    @staticmethod
    async def optimize_scene(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize scene for better performance."""
        project = str(server._validate_project_path(args["project"]))
        optimization_type = args.get("optimization_type", "MESH_CLEANUP")
        settings = args.get("settings", {})

        script_args = {
            "operation": "optimize_scene",
            "project": project,
            "optimization_type": optimization_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        result = await server.blender_executor.execute_script("scene.py", script_args, job_id)

        return {
            "success": True,
            "optimization_type": optimization_type,
            "optimizations": result.get("optimizations", {}),
            "message": f"Scene optimization '{optimization_type}' complete",
        }
