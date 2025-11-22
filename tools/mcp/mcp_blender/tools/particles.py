"""Particle and simulation tools for Blender MCP Server."""

import uuid
from typing import Any, Dict


class ParticleTools:
    """Particle system and simulation tools and handlers."""

    @staticmethod
    def get_tool_definitions() -> list:
        """Get particle and simulation tool definitions."""
        return [
            {
                "name": "add_particle_system",
                "description": "Add particle system to an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Object to add particles to",
                        },
                        "particle_type": {
                            "type": "string",
                            "enum": ["HAIR", "EMITTER"],
                            "default": "EMITTER",
                            "description": "Type of particle system",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "count": {"type": "integer", "default": 1000},
                                "frame_start": {"type": "integer", "default": 1},
                                "frame_end": {"type": "integer", "default": 200},
                                "lifetime": {"type": "integer", "default": 50},
                                "emit_from": {
                                    "type": "string",
                                    "enum": ["VERT", "FACE", "VOLUME"],
                                    "default": "FACE",
                                },
                                "physics_type": {
                                    "type": "string",
                                    "enum": ["NEWTON", "FLUID", "NO"],
                                    "default": "NEWTON",
                                },
                                "velocity": {"type": "number", "default": 2.0},
                                "gravity": {"type": "number", "default": 1.0},
                                "size": {"type": "number", "default": 0.05},
                                "size_random": {"type": "number", "default": 0.0},
                            },
                        },
                    },
                    "required": ["project", "object_name"],
                },
            },
            {
                "name": "add_smoke_simulation",
                "description": "Add smoke or fire simulation to an object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project file path",
                        },
                        "emitter_name": {
                            "type": "string",
                            "description": "Object to emit smoke/fire from",
                        },
                        "domain_name": {
                            "type": "string",
                            "description": "Domain object for simulation",
                            "default": "SmokeDomain",
                        },
                        "simulation_type": {
                            "type": "string",
                            "enum": ["SMOKE", "FIRE", "BOTH"],
                            "default": "SMOKE",
                            "description": "Type of simulation",
                        },
                        "settings": {
                            "type": "object",
                            "properties": {
                                "resolution": {"type": "integer", "default": 32},
                                "density": {"type": "number", "default": 1.0},
                                "temperature": {"type": "number", "default": 1.0},
                                "vorticity": {"type": "number", "default": 2.0},
                                "dissolve_speed": {"type": "integer", "default": 100},
                            },
                        },
                    },
                    "required": ["project", "emitter_name"],
                },
            },
        ]

    @staticmethod
    async def add_particle_system(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add particle system to an object."""
        project = str(server._validate_project_path(args["project"]))
        object_name = args["object_name"]
        particle_type = args.get("particle_type", "EMITTER")
        settings = args.get("settings", {})

        script_args = {
            "operation": "add_particle_system",
            "project": project,
            "object_name": object_name,
            "particle_type": particle_type,
            "settings": settings,
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("particles.py", script_args, job_id)

        return {
            "success": True,
            "object": object_name,
            "particle_type": particle_type,
            "message": f"Particle system added to '{object_name}'",
        }

    @staticmethod
    async def add_smoke_simulation(server, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add smoke or fire simulation."""
        project = str(server._validate_project_path(args["project"]))
        emitter_name = args["emitter_name"]
        domain_name = args.get("domain_name", "SmokeDomain")
        simulation_type = args.get("simulation_type", "SMOKE")
        settings = args.get("settings", {})

        # First create domain
        domain_args = {
            "operation": "add_smoke_domain",
            "project": project,
            "domain_name": domain_name,
            "resolution": settings.get("resolution", 32),
        }

        job_id = str(uuid.uuid4())
        await server.blender_executor.execute_script("particles.py", domain_args, job_id)

        # Then setup emitter
        emitter_args = {
            "operation": "add_smoke_emitter",
            "project": project,
            "object_name": emitter_name,
            "simulation_type": simulation_type,
            "settings": settings,
        }

        await server.blender_executor.execute_script("particles.py", emitter_args, job_id)

        return {
            "success": True,
            "emitter": emitter_name,
            "domain": domain_name,
            "type": simulation_type,
            "message": f"{simulation_type} simulation added to '{emitter_name}'",
        }
