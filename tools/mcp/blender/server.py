#!/usr/bin/env python3
"""Blender MCP Server - 3D content creation, rendering, and simulation."""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from blender.core.asset_manager import AssetManager
from blender.core.blender_executor import BlenderExecutor
from blender.core.job_manager import JobManager
from blender.core.templates import TemplateManager
from core.base_server import BaseMCPServer, ToolRequest, ToolResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BlenderMCPServer(BaseMCPServer):
    """MCP server for Blender operations."""

    def __init__(self, base_dir: str = "/app", port: int = 8017):
        super().__init__(name="blender-mcp", version="1.0.0", port=port)
        self.description = "Blender 3D content creation and rendering"

        # Set up paths
        self.base_dir = Path(base_dir)
        self.projects_dir = self.base_dir / "projects"
        self.assets_dir = self.base_dir / "assets"
        self.outputs_dir = self.base_dir / "outputs"
        self.templates_dir = self.base_dir / "templates"
        self.temp_dir = self.base_dir / "temp"

        # Initialize managers with configured paths
        self.blender_executor = BlenderExecutor(output_dir=str(self.outputs_dir), base_dir=str(self.base_dir))
        self.job_manager = JobManager(str(self.outputs_dir))
        self.asset_manager = AssetManager(str(self.projects_dir), str(self.assets_dir))
        self.template_manager = TemplateManager(str(self.templates_dir))

        # Setup directories
        self.setup_directories()

    def setup_directories(self):
        """Create necessary directories."""
        dirs = [self.projects_dir, self.assets_dir, self.outputs_dir, self.templates_dir, self.temp_dir]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of available tools and their metadata."""
        tools = [
            # Project Management
            {
                "name": "create_blender_project",
                "description": "Create a new Blender project from template",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Project name"},
                        "template": {
                            "type": "string",
                            "enum": ["empty", "basic_scene", "studio_lighting", "procedural", "animation"],
                            "description": "Template to use",
                            "default": "basic_scene",
                        },
                        "settings": {
                            "type": "object",
                            "description": "Project settings",
                            "properties": {
                                "resolution": {"type": "array", "items": {"type": "integer"}, "default": [1920, 1080]},
                                "fps": {"type": "integer", "default": 24},
                                "engine": {"type": "string", "enum": ["CYCLES", "EEVEE", "WORKBENCH"], "default": "CYCLES"},
                            },
                        },
                    },
                    "required": ["name"],
                },
            },
            # Scene Generation
            {
                "name": "add_primitive_objects",
                "description": "Add primitive objects to the scene",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "objects": {
                            "type": "array",
                            "description": "List of objects to add",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["cube", "sphere", "cylinder", "cone", "torus", "plane", "monkey"],
                                        "description": "Object type",
                                    },
                                    "name": {"type": "string", "description": "Object name"},
                                    "location": {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]},
                                    "rotation": {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]},
                                    "scale": {"type": "array", "items": {"type": "number"}, "default": [1, 1, 1]},
                                },
                                "required": ["type"],
                            },
                        },
                    },
                    "required": ["project", "objects"],
                },
            },
            # Lighting
            {
                "name": "setup_lighting",
                "description": "Configure scene lighting",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "type": {
                            "type": "string",
                            "enum": ["three_point", "studio", "hdri", "sun", "area"],
                            "description": "Lighting setup type",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "strength": {"type": "number", "default": 1.0},
                                "color": {"type": "array", "items": {"type": "number"}, "default": [1, 1, 1]},
                                "hdri_path": {"type": "string", "description": "Path to HDRI file (for hdri type)"},
                            },
                        },
                    },
                    "required": ["project", "type"],
                },
            },
            # Materials
            {
                "name": "apply_material",
                "description": "Apply materials to objects",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "object_name": {"type": "string", "description": "Object to apply material to"},
                        "material": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["principled", "emission", "glass", "metal", "plastic", "wood"],
                                    "default": "principled",
                                },
                                "base_color": {"type": "array", "items": {"type": "number"}, "default": [0.8, 0.8, 0.8, 1.0]},
                                "metallic": {"type": "number", "default": 0.0},
                                "roughness": {"type": "number", "default": 0.5},
                                "emission_strength": {"type": "number", "default": 0.0},
                            },
                        },
                    },
                    "required": ["project", "object_name"],
                },
            },
            # Rendering
            {
                "name": "render_image",
                "description": "Render a single frame",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "frame": {"type": "integer", "default": 1},
                        "settings": {
                            "type": "object",
                            "properties": {
                                "resolution": {"type": "array", "items": {"type": "integer"}, "default": [1920, 1080]},
                                "samples": {"type": "integer", "default": 128},
                                "engine": {"type": "string", "enum": ["CYCLES", "EEVEE"], "default": "CYCLES"},
                                "format": {"type": "string", "enum": ["PNG", "JPEG", "EXR", "TIFF"], "default": "PNG"},
                            },
                        },
                    },
                    "required": ["project"],
                },
            },
            {
                "name": "render_animation",
                "description": "Render an animation sequence",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "start_frame": {"type": "integer", "default": 1},
                        "end_frame": {"type": "integer", "default": 250},
                        "settings": {
                            "type": "object",
                            "properties": {
                                "resolution": {"type": "array", "items": {"type": "integer"}, "default": [1920, 1080]},
                                "samples": {"type": "integer", "default": 64},
                                "engine": {"type": "string", "enum": ["CYCLES", "EEVEE"], "default": "EEVEE"},
                                "format": {"type": "string", "enum": ["MP4", "AVI", "MOV", "FRAMES"], "default": "MP4"},
                            },
                        },
                    },
                    "required": ["project"],
                },
            },
            # Physics Simulation
            {
                "name": "setup_physics",
                "description": "Setup physics simulation for objects",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "object_name": {"type": "string", "description": "Object to apply physics to"},
                        "physics_type": {
                            "type": "string",
                            "enum": ["rigid_body", "soft_body", "cloth", "fluid"],
                            "description": "Type of physics simulation",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "mass": {"type": "number", "default": 1.0},
                                "friction": {"type": "number", "default": 0.5},
                                "bounce": {"type": "number", "default": 0.0},
                                "collision_shape": {
                                    "type": "string",
                                    "enum": ["box", "sphere", "convex_hull", "mesh"],
                                    "default": "convex_hull",
                                },
                            },
                        },
                    },
                    "required": ["project", "object_name", "physics_type"],
                },
            },
            {
                "name": "bake_simulation",
                "description": "Bake physics simulation to keyframes",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "start_frame": {"type": "integer", "default": 1},
                        "end_frame": {"type": "integer", "default": 250},
                    },
                    "required": ["project"],
                },
            },
            # Animation
            {
                "name": "create_animation",
                "description": "Create keyframe animation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "object_name": {"type": "string", "description": "Object to animate"},
                        "keyframes": {
                            "type": "array",
                            "description": "List of keyframes",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "frame": {"type": "integer"},
                                    "location": {"type": "array", "items": {"type": "number"}},
                                    "rotation": {"type": "array", "items": {"type": "number"}},
                                    "scale": {"type": "array", "items": {"type": "number"}},
                                },
                                "required": ["frame"],
                            },
                        },
                        "interpolation": {"type": "string", "enum": ["LINEAR", "BEZIER", "CONSTANT"], "default": "BEZIER"},
                    },
                    "required": ["project", "object_name", "keyframes"],
                },
            },
            # Geometry Nodes
            {
                "name": "create_geometry_nodes",
                "description": "Create procedural geometry with nodes",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "object_name": {"type": "string", "description": "Object to apply geometry nodes to"},
                        "node_setup": {
                            "type": "string",
                            "enum": ["scatter", "array", "curve", "volume", "custom"],
                            "description": "Type of geometry node setup",
                        },
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "count": {"type": "integer", "default": 100},
                                "seed": {"type": "integer", "default": 0},
                                "scale_variance": {"type": "number", "default": 0.1},
                            },
                        },
                    },
                    "required": ["project", "object_name", "node_setup"],
                },
            },
            # Job Management
            {
                "name": "get_job_status",
                "description": "Get status of a rendering job",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string", "description": "Job ID to check"}},
                    "required": ["job_id"],
                },
            },
            {
                "name": "get_job_result",
                "description": "Get result of a completed job",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string", "description": "Job ID to retrieve"}},
                    "required": ["job_id"],
                },
            },
            {
                "name": "cancel_job",
                "description": "Cancel a running job",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string", "description": "Job ID to cancel"}},
                    "required": ["job_id"],
                },
            },
            # Asset Management
            {
                "name": "list_projects",
                "description": "List available Blender projects",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "import_model",
                "description": "Import 3D model into project",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "model_path": {"type": "string", "description": "Path to model file"},
                        "format": {
                            "type": "string",
                            "enum": ["FBX", "OBJ", "GLTF", "STL", "PLY"],
                            "description": "Model format",
                        },
                        "location": {"type": "array", "items": {"type": "number"}, "default": [0, 0, 0]},
                    },
                    "required": ["project", "model_path"],
                },
            },
            {
                "name": "export_scene",
                "description": "Export scene to various formats",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project file path"},
                        "format": {
                            "type": "string",
                            "enum": ["FBX", "OBJ", "GLTF", "STL", "USD"],
                            "description": "Export format",
                        },
                        "selected_only": {"type": "boolean", "default": False},
                    },
                    "required": ["project", "format"],
                },
            },
        ]

        # Convert list to dictionary format expected by base class
        tool_dict = {}
        for tool in tools:
            tool_dict[tool["name"]] = {
                "description": tool["description"],
                "parameters": tool["inputSchema"],  # Base class expects 'parameters'
            }

        return tool_dict

    async def execute_tool(self, request: ToolRequest):
        """Execute a tool with given arguments."""
        # Override base class to use our centralized handler

        try:
            name = request.tool
            arguments = request.get_args()
            # Project Management
            if name == "create_blender_project":
                result = await self._create_project(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            # Scene Generation
            elif name == "add_primitive_objects":
                result = await self._add_primitives(arguments)
                return ToolResponse(success=result.get("success", True), result=result)
            elif name == "setup_lighting":
                result = await self._setup_lighting(arguments)
                return ToolResponse(success=result.get("success", True), result=result)
            elif name == "apply_material":
                result = await self._apply_material(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            # Rendering
            elif name == "render_image":
                result = await self._render_image(arguments)
                return ToolResponse(success=result.get("success", True), result=result)
            elif name == "render_animation":
                result = await self._render_animation(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            # Physics
            elif name == "setup_physics":
                result = await self._setup_physics(arguments)
                return ToolResponse(success=result.get("success", True), result=result)
            elif name == "bake_simulation":
                result = await self._bake_simulation(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            # Animation
            elif name == "create_animation":
                result = await self._create_animation(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            # Geometry Nodes
            elif name == "create_geometry_nodes":
                result = await self._create_geometry_nodes(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            # Job Management
            elif name == "get_job_status":
                result = await self._get_job_status(arguments)
                return ToolResponse(success=not bool(result.get("error")), result=result)
            elif name == "get_job_result":
                result = await self._get_job_result(arguments)
                return ToolResponse(success=not bool(result.get("error")), result=result)
            elif name == "cancel_job":
                result = await self._cancel_job(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            # Asset Management
            elif name == "list_projects":
                result = await self._list_projects()
                return ToolResponse(success=result.get("success", True), result=result)
            elif name == "import_model":
                result = await self._import_model(arguments)
                return ToolResponse(success=result.get("success", True), result=result)
            elif name == "export_scene":
                result = await self._export_scene(arguments)
                return ToolResponse(success=result.get("success", True), result=result)

            else:
                return ToolResponse(success=False, result=None, error=f"Unknown tool: {name}")

        except Exception as e:
            logger.error(f"Error in {name}: {str(e)}")
            return ToolResponse(success=False, result=None, error=str(e))

    async def _create_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Blender project."""
        project_name = args["name"]
        template = args.get("template", "basic_scene")
        settings = args.get("settings", {})

        # Generate project path
        project_path = str(self.projects_dir / f"{project_name}.blend")

        # Create project from template
        job_id = str(uuid.uuid4())
        job = self.job_manager.create_job(
            job_id=job_id,
            job_type="create_project",
            parameters={"project_path": project_path, "template": template, "settings": settings},
        )

        # Execute Blender script
        script_args = {"operation": "create_project", "project_path": project_path, "template": template, "settings": settings}

        await self.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        return {
            "success": True,
            "project_path": project_path,
            "job_id": job_id,
            "message": f"Project '{project_name}' created successfully",
        }

    async def _add_primitives(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add primitive objects to scene."""
        project = args["project"]
        objects = args["objects"]

        job_id = str(uuid.uuid4())
        job = self.job_manager.create_job(job_id=job_id, job_type="add_objects", parameters=args)

        script_args = {"operation": "add_primitives", "project": project, "objects": objects}

        await self.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        return {
            "success": True,
            "job_id": job_id,
            "objects_added": len(objects),
            "message": f"Added {len(objects)} objects to scene",
        }

    async def _setup_lighting(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Setup scene lighting."""
        project = args["project"]
        lighting_type = args["type"]
        settings = args.get("settings", {})

        job_id = str(uuid.uuid4())
        script_args = {"operation": "setup_lighting", "project": project, "lighting_type": lighting_type, "settings": settings}

        await self.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        return {"success": True, "lighting_type": lighting_type, "message": f"Lighting setup '{lighting_type}' applied"}

    async def _apply_material(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Apply material to object."""
        project = args["project"]
        object_name = args["object_name"]
        material = args.get("material", {})

        job_id = str(uuid.uuid4())
        script_args = {"operation": "apply_material", "project": project, "object_name": object_name, "material": material}

        await self.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "material_type": material.get("type", "principled"),
            "message": f"Material applied to '{object_name}'",
        }

    async def _render_image(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Render a single frame."""
        project = args["project"]
        frame = args.get("frame", 1)
        settings = args.get("settings", {})

        # Create render job
        job_id = str(uuid.uuid4())
        job = self.job_manager.create_job(job_id=job_id, job_type="render_image", parameters=args)

        # Start async rendering
        script_args = {
            "operation": "render_image",
            "project": project,
            "frame": frame,
            "settings": settings,
            "output_path": str(self.outputs_dir / f"{job_id}.png"),
        }

        # This runs asynchronously
        asyncio.create_task(self.blender_executor.execute_script("render.py", script_args, job_id))

        return {
            "success": True,
            "job_id": job_id,
            "status": "QUEUED",
            "message": "Render job started",
            "check_status": f"/jobs/{job_id}/status",
        }

    async def _render_animation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Render animation sequence."""
        project = args["project"]
        start_frame = args.get("start_frame", 1)
        end_frame = args.get("end_frame", 250)
        settings = args.get("settings", {})

        # Create render job
        job_id = str(uuid.uuid4())
        job = self.job_manager.create_job(job_id=job_id, job_type="render_animation", parameters=args)

        script_args = {
            "operation": "render_animation",
            "project": project,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "settings": settings,
            "output_path": str(self.outputs_dir / job_id) + "/",
        }

        # Start async rendering
        asyncio.create_task(self.blender_executor.execute_script("render.py", script_args, job_id))

        return {
            "success": True,
            "job_id": job_id,
            "status": "QUEUED",
            "frames": end_frame - start_frame + 1,
            "message": "Animation render job started",
            "check_status": f"/jobs/{job_id}/status",
        }

    async def _setup_physics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Setup physics simulation."""
        project = args["project"]
        object_name = args["object_name"]
        physics_type = args["physics_type"]
        settings = args.get("settings", {})

        script_args = {
            "operation": "setup_physics",
            "project": project,
            "object_name": object_name,
            "physics_type": physics_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        await self.blender_executor.execute_script("physics_sim.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "physics_type": physics_type,
            "message": f"Physics '{physics_type}' applied to '{object_name}'",
        }

    async def _bake_simulation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Bake physics simulation."""
        project = args["project"]
        start_frame = args.get("start_frame", 1)
        end_frame = args.get("end_frame", 250)

        job_id = str(uuid.uuid4())
        job = self.job_manager.create_job(job_id=job_id, job_type="bake_simulation", parameters=args)

        script_args = {"operation": "bake_simulation", "project": project, "start_frame": start_frame, "end_frame": end_frame}

        asyncio.create_task(self.blender_executor.execute_script("physics_sim.py", script_args, job_id))

        return {
            "success": True,
            "job_id": job_id,
            "status": "RUNNING",
            "message": f"Baking simulation frames {start_frame}-{end_frame}",
        }

    async def _create_animation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create keyframe animation."""
        project = args["project"]
        object_name = args["object_name"]
        keyframes = args["keyframes"]
        interpolation = args.get("interpolation", "BEZIER")

        script_args = {
            "operation": "create_animation",
            "project": project,
            "object_name": object_name,
            "keyframes": keyframes,
            "interpolation": interpolation,
        }

        job_id = str(uuid.uuid4())
        await self.blender_executor.execute_script("animation.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "keyframes_count": len(keyframes),
            "message": f"Animation created with {len(keyframes)} keyframes",
        }

    async def _create_geometry_nodes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create geometry nodes setup."""
        project = args["project"]
        object_name = args["object_name"]
        node_setup = args["node_setup"]
        parameters = args.get("parameters", {})

        script_args = {
            "operation": "create_geometry_nodes",
            "project": project,
            "object_name": object_name,
            "node_setup": node_setup,
            "parameters": parameters,
        }

        job_id = str(uuid.uuid4())
        await self.blender_executor.execute_script("geometry_nodes.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "node_setup": node_setup,
            "message": f"Geometry nodes '{node_setup}' applied to '{object_name}'",
        }

    async def _get_job_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get job status."""
        job_id = args["job_id"]
        job = self.job_manager.get_job(job_id)

        if not job:
            return {"error": f"Job {job_id} not found"}

        return {
            "job_id": job_id,
            "status": job["status"],
            "progress": job.get("progress", 0),
            "message": job.get("message", ""),
            "created_at": job["created_at"],
            "updated_at": job.get("updated_at"),
        }

    async def _get_job_result(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get job result."""
        job_id = args["job_id"]
        job = self.job_manager.get_job(job_id)

        if not job:
            return {"error": f"Job {job_id} not found"}

        if job["status"] != "COMPLETED":
            return {"error": f"Job {job_id} not completed", "status": job["status"]}

        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "result": job.get("result", {}),
            "output_path": job.get("output_path"),
        }

    async def _cancel_job(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a running job."""
        job_id = args["job_id"]

        success = self.job_manager.cancel_job(job_id)

        if success:
            # Also kill the Blender process
            self.blender_executor.kill_process(job_id)
            return {"success": True, "message": f"Job {job_id} cancelled"}
        else:
            return {"error": f"Could not cancel job {job_id}"}

    async def _list_projects(self) -> Dict[str, Any]:
        """List available projects."""
        projects = self.asset_manager.list_projects()

        return {"success": True, "projects": projects, "count": len(projects)}

    async def _import_model(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Import 3D model."""
        project = args["project"]
        model_path = args["model_path"]
        format = self.asset_manager.detect_format(model_path)
        location = args.get("location", [0, 0, 0])

        script_args = {
            "operation": "import_model",
            "project": project,
            "model_path": model_path,
            "format": format,
            "location": location,
        }

        job_id = str(uuid.uuid4())
        await self.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        return {"success": True, "model_path": model_path, "format": format, "message": f"Model imported from '{model_path}'"}

    async def _export_scene(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Export scene to format."""
        project = args["project"]
        export_format = args["format"]
        selected_only = args.get("selected_only", False)

        output_path = str(self.outputs_dir / f"{Path(project).stem}.{export_format.lower()}")

        script_args = {
            "operation": "export_scene",
            "project": project,
            "format": export_format,
            "output_path": output_path,
            "selected_only": selected_only,
        }

        job_id = str(uuid.uuid4())
        await self.blender_executor.execute_script("scene_builder.py", script_args, job_id)

        return {
            "success": True,
            "output_path": output_path,
            "format": export_format,
            "message": f"Scene exported to '{output_path}'",
        }


def main():
    """Main entry point."""
    server = BlenderMCPServer()
    server.run()


if __name__ == "__main__":
    main()
