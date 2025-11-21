"""Texture and UV tools for Blender MCP Server."""

import uuid
from typing import Any, Dict


class TextureTools:
    """Texture and UV mapping tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get texture and UV tool definitions."""
        return [
            {
                "name": "add_texture",
                "description": "Add texture to a material",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Object to add texture to",
                        },
                        "texture_type": {
                            "type": "string",
                            "enum": [
                                "IMAGE",
                                "NOISE",
                                "VORONOI",
                                "MUSGRAVE",
                                "WAVE",
                                "MAGIC",
                                "BRICK",
                                "CHECKER",
                            ],
                            "description": "Type of texture",
                        },
                        "texture_settings": {
                            "type": "object",
                            "properties": {
                                "image_path": {
                                    "type": "string",
                                    "description": "Path to image file (for IMAGE type)",
                                },
                                "scale": {"type": "number", "default": 1.0},
                                "detail": {"type": "number", "default": 2.0},
                                "roughness": {"type": "number", "default": 0.5},
                                "mapping": {
                                    "type": "string",
                                    "enum": ["UV", "GENERATED", "OBJECT"],
                                    "default": "UV",
                                },
                            },
                        },
                    },
                    "required": ["project", "object_name", "texture_type"],
                },
            },
            {
                "name": "add_uv_map",
                "description": "Add UV mapping to an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Object to add UV map to",
                        },
                        "uv_type": {
                            "type": "string",
                            "enum": [
                                "SMART_PROJECT",
                                "CUBE_PROJECT",
                                "CYLINDER_PROJECT",
                                "SPHERE_PROJECT",
                                "PROJECT_FROM_VIEW",
                            ],
                            "default": "SMART_PROJECT",
                            "description": "Type of UV projection",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "angle_limit": {"type": "number", "default": 66.0},
                                "island_margin": {"type": "number", "default": 0.0},
                                "area_weight": {"type": "number", "default": 0.0},
                            },
                        },
                    },
                    "required": ["project", "object_name"],
                },
            },
        ]

    @staticmethod
    async def add_texture(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add texture to an object's material."""
        project = str(server._validate_project_path(args["project"]))
        object_name = args["object_name"]
        texture_type = args["texture_type"]
        texture_settings = args.get("texture_settings", {})

        script_args = {
            "operation": "add_texture",
            "project": project,
            "object_name": object_name,
            "texture_type": texture_type,
            "settings": texture_settings,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("textures.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "texture_type": texture_type,
            "message": f"Texture '{texture_type}' added to '{object_name}'",
        }

    @staticmethod
    async def add_uv_map(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add UV mapping to an object."""
        project = str(server._validate_project_path(args["project"]))
        object_name = args["object_name"]
        uv_type = args.get("uv_type", "SMART_PROJECT")
        settings = args.get("settings", {})

        script_args = {
            "operation": "add_uv_map",
            "project": project,
            "object_name": object_name,
            "uv_type": uv_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("textures.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "uv_type": uv_type,
            "message": f"UV map '{uv_type}' added to '{object_name}'",
        }
