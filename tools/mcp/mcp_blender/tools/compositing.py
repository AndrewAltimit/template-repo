"""Compositing and rendering tools for Blender MCP Server."""

import uuid
from typing import Any, Dict


class CompositingTools:
    """Compositing and rendering tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get compositing and rendering tool definitions."""
        return [
            {
                "name": "setup_compositor",
                "description": "Setup compositor nodes for post-processing",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "compositor_type": {
                            "type": "string",
                            "enum": [
                                "BASIC",
                                "DENOISING",
                                "COLOR_GRADING",
                                "GLARE",
                                "FOG_GLOW",
                                "LENS_DISTORTION",
                                "VIGNETTE",
                            ],
                            "default": "BASIC",
                            "description": "Type of compositor setup",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                # Color grading
                                "exposure": {"type": "number", "default": 0.0},
                                "gamma": {"type": "number", "default": 1.0},
                                "contrast": {"type": "number", "default": 0.0},
                                "saturation": {"type": "number", "default": 1.0},
                                # Glare
                                "glare_type": {
                                    "type": "string",
                                    "enum": ["GHOSTS", "STREAKS", "FOG_GLOW", "SIMPLE_STAR"],
                                    "default": "GHOSTS",
                                },
                                "glare_threshold": {"type": "number", "default": 1.0},
                                # Vignette
                                "vignette_amount": {"type": "number", "default": 0.5},
                            },
                        },
                    },
                    "required": ["project"],
                },
            },
            {
                "name": "batch_render",
                "description": "Render multiple frames or scenes in batch",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "render_type": {
                            "type": "string",
                            "enum": ["ANIMATION", "STILL_FRAMES", "CAMERAS", "LAYERS"],
                            "default": "ANIMATION",
                            "description": "Type of batch render",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "frame_start": {"type": "integer", "default": 1},
                                "frame_end": {"type": "integer", "default": 250},
                                "frame_step": {"type": "integer", "default": 1},
                                "frames": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Specific frames to render",
                                },
                                "cameras": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Camera names for multi-camera render",
                                },
                                "output_format": {
                                    "type": "string",
                                    "enum": ["PNG", "JPEG", "EXR", "TIFF"],
                                    "default": "PNG",
                                },
                                "output_path": {
                                    "type": "string",
                                    "description": "Output directory path",
                                },
                            },
                        },
                    },
                    "required": ["project"],
                },
            },
        ]

    @staticmethod
    async def setup_compositor(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Setup compositor nodes for post-processing."""
        project = str(server._validate_project_path(args["project"]))
        compositor_type = args.get("compositor_type", "BASIC")
        settings = args.get("settings", {})

        script_args = {
            "operation": "setup_compositor",
            "project": project,
            "compositor_type": compositor_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("compositing.py", script_args, job_id)

        return {
            "success": True,
            "compositor_type": compositor_type,
            "message": f"Compositor setup '{compositor_type}' applied",
        }

    @staticmethod
    async def batch_render(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute batch rendering operation."""
        project = str(server._validate_project_path(args["project"]))
        render_type = args.get("render_type", "ANIMATION")
        settings = args.get("settings", {})

        # Validate output path if provided
        if "output_path" in settings:
            output_path = str(server._validate_path(settings["output_path"], server.outputs_dir, "directory"))
            settings["output_path"] = output_path

        script_args = {
            "operation": "batch_render",
            "project": project,
            "render_type": render_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        server.job_manager.create_job(job_id=job_id, job_type="batch_render", parameters=script_args)

        # Start async render
        await server.blender_executor.execute_script("render.py", script_args, job_id)

        return {
            "success": True,
            "job_id": job_id,
            "render_type": render_type,
            "message": f"Batch render job '{job_id}' started",
        }
