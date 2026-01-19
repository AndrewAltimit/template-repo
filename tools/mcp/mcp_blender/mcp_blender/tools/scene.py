"""Scene management tools for Blender MCP Server."""


# Tool modules access internal server validation methods by design.
# This is an intentional internal package architecture pattern.

from typing import Any, Dict
import uuid


class SceneTools:
    """Scene analysis and optimization tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get scene management tool definitions."""
        return [
            {
                "name": "delete_objects",
                "description": "Delete objects from the scene by name, type, or pattern",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "object_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of object names to delete",
                        },
                        "object_types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "MESH",
                                    "LIGHT",
                                    "CAMERA",
                                    "EMPTY",
                                    "CURVE",
                                    "SURFACE",
                                    "ARMATURE",
                                ],
                            },
                            "description": "Delete all objects of these types",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Wildcard pattern to match names (e.g., 'Ground*')",
                        },
                    },
                    "required": ["project"],
                },
            },
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
            {
                "name": "create_curve",
                "description": "Create Bézier curves for growth paths and spatial guides",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "name": {
                            "type": "string",
                            "default": "GrowthPath",
                            "description": "Name for the curve object",
                        },
                        "curve_type": {
                            "type": "string",
                            "enum": ["BEZIER", "NURBS", "POLY"],
                            "default": "BEZIER",
                            "description": "Type of curve",
                        },
                        "points": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "number"},
                            },
                            "description": "Control points [[x, y, z], ...]",
                        },
                        "closed": {
                            "type": "boolean",
                            "default": False,
                            "description": "Close the curve into a loop",
                        },
                        "resolution": {
                            "type": "integer",
                            "default": 12,
                            "description": "Curve resolution",
                        },
                        "bevel_depth": {
                            "type": "number",
                            "default": 0.0,
                            "description": "Bevel depth for 3D curve",
                        },
                        "target_object": {
                            "type": "string",
                            "description": "Project curve onto this object's surface",
                        },
                        "surface_offset": {
                            "type": "number",
                            "default": 0.05,
                            "description": "Offset from target surface",
                        },
                    },
                    "required": ["project"],
                },
            },
        ]

    @staticmethod
    async def delete_objects(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delete objects from the scene by name, type, or pattern."""
        import asyncio
        import json
        from pathlib import Path

        project = str(server._validate_project_path(args["project"]))
        object_names = args.get("object_names", [])
        object_types = args.get("object_types", [])
        pattern = args.get("pattern")

        script_args = {
            "operation": "delete_objects",
            "project": project,
            "object_names": object_names,
            "object_types": object_types,
            "pattern": pattern,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        # Wait briefly for the quick operation to complete and read result
        deleted_objects = []
        result_file = Path(server.blender_executor.output_dir) / "jobs" / f"{job_id}.result"

        # Poll for result file (delete_objects is typically fast)
        for _ in range(10):  # Wait up to 5 seconds
            await asyncio.sleep(0.5)
            if result_file.exists():
                try:
                    result_data = json.loads(result_file.read_text())
                    deleted_objects = result_data.get("deleted_objects", [])
                    # Clean up result file
                    result_file.unlink(missing_ok=True)
                    break
                except (json.JSONDecodeError, OSError):
                    pass

        return {
            "success": True,
            "message": f"Deleted {len(deleted_objects)} object(s)",
            "deleted_objects": deleted_objects,
            "requested_names": object_names,
            "requested_types": object_types,
            "requested_pattern": pattern,
        }

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

    @staticmethod
    async def create_curve(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create Bézier curves for growth paths and spatial guides."""
        project = str(server._validate_project_path(args["project"]))
        name = args.get("name", "GrowthPath")
        curve_type = args.get("curve_type", "BEZIER")
        points = args.get("points")
        closed = args.get("closed", False)
        resolution = args.get("resolution", 12)
        bevel_depth = args.get("bevel_depth", 0.0)
        target_object = args.get("target_object")
        surface_offset = args.get("surface_offset", 0.05)

        script_args = {
            "operation": "create_curve",
            "project": project,
            "name": name,
            "curve_type": curve_type,
            "points": points,
            "closed": closed,
            "resolution": resolution,
            "bevel_depth": bevel_depth,
            "target_object": target_object,
            "surface_offset": surface_offset,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        return {
            "success": True,
            "message": f"Created curve '{name}' with {len(points) if points else 3} points",
            "curve_name": name,
            "curve_type": curve_type,
        }
