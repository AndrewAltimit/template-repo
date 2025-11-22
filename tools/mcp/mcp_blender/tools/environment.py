"""Environment and world tools for Blender MCP Server."""

import uuid
from typing import Any, Dict


class EnvironmentTools:
    """World environment tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get environment tool definitions."""
        return [
            {
                "name": "setup_world_environment",
                "description": "Setup world environment (HDRI, sky, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "environment_type": {
                            "type": "string",
                            "enum": ["HDRI", "SKY_TEXTURE", "GRADIENT", "COLOR", "VOLUMETRIC"],
                            "default": "SKY_TEXTURE",
                            "description": "Type of environment",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "hdri_path": {
                                    "type": "string",
                                    "description": "Path to HDRI image",
                                },
                                "strength": {"type": "number", "default": 1.0},
                                "rotation": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "default": [0, 0, 0],
                                    "description": "Environment rotation [x, y, z]",
                                },
                                # Sky texture settings
                                "sun_direction": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "default": [0, 0, 1],
                                },
                                "turbidity": {"type": "number", "default": 2.2},
                                "ground_albedo": {"type": "number", "default": 0.3},
                                # Gradient settings
                                "color_top": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "default": [0.5, 0.7, 1.0, 1.0],
                                },
                                "color_bottom": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "default": [0.2, 0.2, 0.3, 1.0],
                                },
                                # Volumetric settings
                                "volume_density": {"type": "number", "default": 0.1},
                                "volume_anisotropy": {"type": "number", "default": 0.0},
                            },
                        },
                    },
                    "required": ["project"],
                },
            },
        ]

    @staticmethod
    async def setup_world_environment(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Setup world environment lighting and atmosphere."""
        project = str(server._validate_project_path(args["project"]))
        environment_type = args.get("environment_type", "SKY_TEXTURE")
        settings = args.get("settings", {})

        # Validate HDRI path if provided
        if environment_type == "HDRI" and "hdri_path" in settings:
            hdri_path = str(server._validate_path(settings["hdri_path"], server.assets_dir, "file"))
            settings["hdri_path"] = hdri_path

        script_args = {
            "operation": "setup_world_environment",
            "project": project,
            "environment_type": environment_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("environment.py", script_args, job_id)

        return {
            "success": True,
            "environment_type": environment_type,
            "message": f"World environment '{environment_type}' configured",
        }
