"""Blender MCP Server tools package."""

from .camera import CameraTools
from .compositing import CompositingTools
from .environment import EnvironmentTools
from .modifiers import ModifierTools
from .particles import ParticleTools
from .scene import SceneTools
from .textures import TextureTools

__all__ = [
    "CameraTools",
    "ModifierTools",
    "ParticleTools",
    "TextureTools",
    "CompositingTools",
    "SceneTools",
    "EnvironmentTools",
    "TOOLS",
]

# Tool registry - exported for compatibility with CI tests
# Maps tool names to their handler classes for discovery
TOOLS = {
    # Camera tools
    "setup_camera": CameraTools,
    "add_camera_track": CameraTools,
    # Modifier tools
    "add_modifier": ModifierTools,
    # Particle tools
    "add_particle_system": ParticleTools,
    "add_smoke_simulation": ParticleTools,
    # Texture tools
    "add_texture": TextureTools,
    "add_uv_map": TextureTools,
    # Compositing tools
    "setup_compositor": CompositingTools,
    "batch_render": CompositingTools,
    # Scene tools
    "delete_objects": SceneTools,
    "analyze_scene": SceneTools,
    "optimize_scene": SceneTools,
    # Environment tools
    "setup_world_environment": EnvironmentTools,
}


def get_all_tool_definitions():
    """Get all tool definitions from all modules."""
    tools = []
    tools.extend(CameraTools.get_tool_definitions())
    tools.extend(ModifierTools.get_tool_definitions())
    tools.extend(ParticleTools.get_tool_definitions())
    tools.extend(TextureTools.get_tool_definitions())
    tools.extend(CompositingTools.get_tool_definitions())
    tools.extend(SceneTools.get_tool_definitions())
    tools.extend(EnvironmentTools.get_tool_definitions())
    return tools


def get_tool_handlers():
    """Get mapping of tool names to their handler methods."""
    return {
        # Camera tools
        "setup_camera": CameraTools.setup_camera,
        "add_camera_track": CameraTools.add_camera_track,
        # Modifier tools
        "add_modifier": ModifierTools.add_modifier,
        # Particle tools
        "add_particle_system": ParticleTools.add_particle_system,
        "add_smoke_simulation": ParticleTools.add_smoke_simulation,
        # Texture tools
        "add_texture": TextureTools.add_texture,
        "add_uv_map": TextureTools.add_uv_map,
        # Compositing tools
        "setup_compositor": CompositingTools.setup_compositor,
        "batch_render": CompositingTools.batch_render,
        # Scene tools
        "delete_objects": SceneTools.delete_objects,
        "analyze_scene": SceneTools.analyze_scene,
        "optimize_scene": SceneTools.optimize_scene,
        # Environment tools
        "setup_world_environment": EnvironmentTools.setup_world_environment,
    }
