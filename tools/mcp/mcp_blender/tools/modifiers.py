"""Modifier tools for Blender MCP Server."""

import uuid
from typing import Any, Dict


class ModifierTools:
    """Modifier-related tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get modifier tool definitions."""
        return [
            {
                "name": "add_modifier",
                "description": "Add modifier to an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Object to add modifier to",
                        },
                        "modifier_type": {
                            "type": "string",
                            "enum": [
                                "SUBSURF",
                                "ARRAY",
                                "MIRROR",
                                "SOLIDIFY",
                                "BEVEL",
                                "DECIMATE",
                                "REMESH",
                                "SMOOTH",
                                "WAVE",
                                "DISPLACE",
                            ],
                            "description": "Type of modifier",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                # Subdivision Surface
                                "levels": {"type": "integer", "default": 2},
                                "render_levels": {"type": "integer", "default": 3},
                                # Array
                                "count": {"type": "integer", "default": 3},
                                "relative_offset": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "default": [1, 0, 0],
                                },
                                # Mirror
                                "use_axis": {
                                    "type": "array",
                                    "items": {"type": "boolean"},
                                    "default": [True, False, False],
                                },
                                # Solidify
                                "thickness": {"type": "number", "default": 0.1},
                                # Bevel
                                "width": {"type": "number", "default": 0.1},
                                "segments": {"type": "integer", "default": 2},
                                # Wave
                                "height": {"type": "number", "default": 1.0},
                                "width_wave": {"type": "number", "default": 1.0},
                                "speed": {"type": "number", "default": 1.0},
                            },
                        },
                    },
                    "required": ["project", "object_name", "modifier_type"],
                },
            },
        ]

    @staticmethod
    async def add_modifier(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add modifier to an object."""
        project = str(server._validate_project_path(args["project"]))
        object_name = args["object_name"]
        modifier_type = args["modifier_type"]
        settings = args.get("settings", {})

        script_args = {
            "operation": "add_modifier",
            "project": project,
            "object_name": object_name,
            "modifier_type": modifier_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("modifiers.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "modifier": modifier_type,
            "message": f"Modifier '{modifier_type}' added to '{object_name}'",
        }
