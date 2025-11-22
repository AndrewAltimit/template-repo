"""Camera tools for Blender MCP Server."""

import uuid
from typing import Any, Dict


class CameraTools:
    """Camera-related tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get camera tool definitions."""
        return [
            {
                "name": "setup_camera",
                "description": "Setup and configure camera in the scene",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "camera_name": {
                            "type": "string",
                            "description": "Name for the camera",
                            "default": "Camera",
                        },
                        "location": {
                            "type": "array",
                            "items": {"type": "number"},
                            "default": [7, -7, 5],
                            "description": "Camera location [x, y, z]",
                        },
                        "rotation": {
                            "type": "array",
                            "items": {"type": "number"},
                            "default": [1.1, 0, 0.785],
                            "description": "Camera rotation in radians [x, y, z]",
                        },
                        "focal_length": {
                            "type": "number",
                            "default": 50,
                            "description": "Camera focal length in mm",
                        },
                        "depth_of_field": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean", "default": False},
                                "focus_distance": {"type": "number", "default": 10},
                                "f_stop": {"type": "number", "default": 2.8},
                            },
                        },
                    },
                    "required": ["project"],
                },
            },
            {
                "name": "add_camera_track",
                "description": "Add tracking constraint to make camera follow an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "camera_name": {
                            "type": "string",
                            "description": "Camera to add tracking to",
                            "default": "Camera",
                        },
                        "target_object": {
                            "type": "string",
                            "description": "Object for camera to track",
                        },
                        "track_type": {
                            "type": "string",
                            "enum": ["TRACK_TO", "DAMPED_TRACK", "LOCKED_TRACK"],
                            "default": "TRACK_TO",
                            "description": "Type of tracking constraint",
                        },
                    },
                    "required": ["project", "target_object"],
                },
            },
        ]

    @staticmethod
    async def setup_camera(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Setup camera in the scene."""
        project = str(server._validate_project_path(args["project"]))
        camera_name = args.get("camera_name", "Camera")
        location = args.get("location", [7, -7, 5])
        rotation = args.get("rotation", [1.1, 0, 0.785])
        focal_length = args.get("focal_length", 50)
        dof = args.get("depth_of_field", {})

        script_args = {
            "operation": "setup_camera",
            "project": project,
            "camera_name": camera_name,
            "location": location,
            "rotation": rotation,
            "focal_length": focal_length,
            "depth_of_field": dof,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("camera_tools.py", script_args, job_id)

        return {
            "success": True,
            "camera_name": camera_name,
            "message": f"Camera '{camera_name}' configured successfully",
        }

    @staticmethod
    async def add_camera_track(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add tracking constraint to camera."""
        project = str(server._validate_project_path(args["project"]))
        camera_name = args.get("camera_name", "Camera")
        target_object = args["target_object"]
        track_type = args.get("track_type", "TRACK_TO")

        script_args = {
            "operation": "add_camera_track",
            "project": project,
            "camera_name": camera_name,
            "target_object": target_object,
            "track_type": track_type,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("camera_tools.py", script_args, job_id)

        return {
            "success": True,
            "camera_name": camera_name,
            "target": target_object,
            "message": f"Camera tracking added to '{camera_name}'",
        }
