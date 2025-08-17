"""Template management for Blender projects."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TemplateManager:
    """Manages Blender project templates."""

    def __init__(self, templates_dir: str = "/app/templates"):
        """Initialize template manager.

        Args:
            templates_dir: Directory containing template files
        """
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Template definitions
        self.templates = {
            "empty": {
                "name": "Empty Scene",
                "description": "Blank Blender project with default settings",
                "settings": {
                    "engine": "CYCLES",
                    "samples": 128,
                    "resolution": [1920, 1080],
                    "fps": 24,
                },
            },
            "basic_scene": {
                "name": "Basic Scene",
                "description": "Simple scene with camera, light, and ground plane",
                "settings": {
                    "engine": "CYCLES",
                    "samples": 128,
                    "resolution": [1920, 1080],
                    "fps": 24,
                },
                "objects": [
                    {
                        "type": "plane",
                        "name": "Ground",
                        "location": [0, 0, 0],
                        "scale": [10, 10, 1],
                    }
                ],
                "lights": [
                    {
                        "type": "sun",
                        "name": "Sun",
                        "strength": 5.0,
                        "rotation": [0.785, 0, 0.785],
                    }
                ],
                "camera": {"location": [7, -7, 5], "rotation": [1.1, 0, 0.785]},
            },
            "studio_lighting": {
                "name": "Studio Lighting",
                "description": "Professional three-point lighting setup",
                "settings": {
                    "engine": "CYCLES",
                    "samples": 256,
                    "resolution": [1920, 1080],
                    "fps": 24,
                    "film_transparent": True,
                },
                "lights": [
                    {
                        "type": "area",
                        "name": "Key Light",
                        "location": [3, -3, 3],
                        "rotation": [1.2, 0, 0.6],
                        "strength": 500,
                        "size": 2.0,
                    },
                    {
                        "type": "area",
                        "name": "Fill Light",
                        "location": [-3, -2, 2],
                        "rotation": [1.3, 0, -0.8],
                        "strength": 200,
                        "size": 3.0,
                    },
                    {
                        "type": "area",
                        "name": "Rim Light",
                        "location": [0, 4, 2],
                        "rotation": [-0.5, 0, 0],
                        "strength": 300,
                        "size": 1.5,
                    },
                ],
                "camera": {
                    "location": [4, -4, 2],
                    "rotation": [1.4, 0, 0.785],
                    "focal_length": 85,
                },
                "world": {
                    "use_nodes": True,
                    "background_color": [0.05, 0.05, 0.05],
                    "background_strength": 1.0,
                },
            },
            "procedural": {
                "name": "Procedural Setup",
                "description": "Scene prepared for procedural generation",
                "settings": {
                    "engine": "EEVEE",
                    "samples": 64,
                    "resolution": [1920, 1080],
                    "fps": 30,
                },
                "modifiers": {
                    "subdivision": True,
                    "array": True,
                    "geometry_nodes": True,
                },
            },
            "animation": {
                "name": "Animation Ready",
                "description": "Scene configured for animation work",
                "settings": {
                    "engine": "EEVEE",
                    "samples": 32,
                    "resolution": [1920, 1080],
                    "fps": 24,
                    "frame_start": 1,
                    "frame_end": 250,
                },
                "timeline": {
                    "auto_keying": True,
                    "frame_rate": 24,
                    "time_unit": "FRAMES",
                },
            },
            "physics": {
                "name": "Physics Simulation",
                "description": "Scene ready for physics simulations",
                "settings": {
                    "engine": "EEVEE",
                    "samples": 32,
                    "resolution": [1920, 1080],
                    "fps": 30,
                    "frame_end": 500,
                },
                "physics": {
                    "gravity": [0, 0, -9.81],
                    "scene_scale": 1.0,
                    "collision_margin": 0.04,
                },
                "objects": [
                    {
                        "type": "plane",
                        "name": "Ground",
                        "location": [0, 0, 0],
                        "scale": [20, 20, 1],
                        "physics": {"type": "passive", "collision_shape": "mesh"},
                    }
                ],
            },
            "architectural": {
                "name": "Architectural Visualization",
                "description": "Setup for architectural rendering",
                "settings": {
                    "engine": "CYCLES",
                    "samples": 512,
                    "resolution": [3840, 2160],
                    "fps": 24,
                    "use_denoising": True,
                },
                "camera": {"type": "PERSP", "focal_length": 24, "sensor_width": 36},
                "world": {
                    "hdri": "studio_small_09_4k.hdr",
                    "hdri_strength": 1.0,
                    "hdri_rotation": [0, 0, 0],
                },
            },
            "product": {
                "name": "Product Visualization",
                "description": "Clean setup for product renders",
                "settings": {
                    "engine": "CYCLES",
                    "samples": 256,
                    "resolution": [2048, 2048],
                    "fps": 24,
                    "film_transparent": True,
                },
                "lights": [
                    {
                        "type": "hdri",
                        "hdri_path": "studio_small_03_4k.hdr",
                        "strength": 0.5,
                    }
                ],
                "camera": {
                    "type": "ORTHO",
                    "ortho_scale": 3.0,
                    "location": [0, -5, 0],
                    "rotation": [1.5708, 0, 0],
                },
            },
            "vfx": {
                "name": "VFX Compositing",
                "description": "Setup for visual effects and compositing",
                "settings": {
                    "engine": "CYCLES",
                    "samples": 128,
                    "resolution": [1920, 1080],
                    "fps": 24,
                    "use_motion_blur": True,
                    "use_compositing": True,
                },
                "compositing": {"use_nodes": True, "backdrop": True},
                "tracking": {"enabled": True},
            },
            "game_asset": {
                "name": "Game Asset",
                "description": "Optimized for game asset creation",
                "settings": {
                    "engine": "EEVEE",
                    "samples": 16,
                    "resolution": [1024, 1024],
                    "fps": 30,
                },
                "export": {
                    "format": "FBX",
                    "apply_modifiers": True,
                    "triangulate": True,
                },
            },
            "sculpting": {
                "name": "Sculpting",
                "description": "Prepared for digital sculpting",
                "settings": {
                    "engine": "WORKBENCH",
                    "shading": "MATCAP",
                    "resolution": [1920, 1080],
                },
                "sculpt": {
                    "dyntopo": True,
                    "symmetry_x": True,
                    "matcap": "clay_brown.exr",
                },
            },
        }

        # Create default template files if they don't exist
        self._create_default_templates()

    def _create_default_templates(self):
        """Create default template .blend files if they don't exist."""
        # This would ideally create actual .blend files
        # For now, we'll create JSON descriptions
        for template_id, template_data in self.templates.items():
            template_file = self.templates_dir / f"{template_id}.json"
            if not template_file.exists():
                try:
                    template_file.write_text(json.dumps(template_data, indent=2))
                except PermissionError:
                    logger.warning(f"Could not create template {template_id}.json - permission denied. Continuing without it.")

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get template configuration.

        Args:
            template_id: Template identifier

        Returns:
            Template configuration or None
        """
        if template_id in self.templates:
            return dict(self.templates[template_id])  # type: ignore

        # Try loading from file
        template_file = self.templates_dir / f"{template_id}.json"
        if template_file.exists():
            try:
                data = json.loads(template_file.read_text())
                if not isinstance(data, dict):
                    raise TypeError(f"Template data is not a dictionary: {type(data)}")
                return data  # type: ignore
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Failed to load or parse template {template_id}: {e}")

        return None

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates.

        Returns:
            List of template information
        """
        template_list = []

        for template_id, template_data in self.templates.items():
            template_list.append(
                {
                    "id": template_id,
                    "name": template_data.get("name", template_id) if isinstance(template_data, dict) else template_id,
                    "description": template_data.get("description", "") if isinstance(template_data, dict) else "",
                    "engine": (
                        template_data.get("settings", {}).get("engine", "CYCLES")
                        if isinstance(template_data, dict)
                        else "CYCLES"
                    ),
                }
            )

        return template_list

    def create_from_template(
        self,
        template_id: str,
        output_path: str,
        custom_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new project from template.

        Args:
            template_id: Template to use
            output_path: Path for new project
            custom_settings: Optional settings to override

        Returns:
            Creation result
        """
        template = self.get_template(template_id)

        if not template:
            return {"error": f"Template '{template_id}' not found"}

        # Merge custom settings
        if custom_settings:
            settings = template.get("settings", {})
            settings.update(custom_settings)
            template["settings"] = settings

        # Check for template .blend file
        template_blend = self.templates_dir / f"{template_id}.blend"
        output = Path(output_path)

        if template_blend.exists():
            # Copy template file
            try:
                shutil.copy2(template_blend, output)
                return {
                    "success": True,
                    "project_path": str(output),
                    "template": template_id,
                    "message": f"Project created from template '{template_id}'",
                }
            except Exception as e:
                logger.error(f"Failed to copy template: {e}")
                return {"error": str(e)}
        else:
            # Return template configuration for script-based creation
            return {
                "success": True,
                "template_config": template,
                "template_id": template_id,
                "output_path": str(output),
            }

    def save_as_template(self, project_path: str, template_name: str, description: str = "") -> Dict[str, Any]:
        """Save an existing project as a template.

        Args:
            project_path: Path to project file
            template_name: Name for the template
            description: Template description

        Returns:
            Save result
        """
        source = Path(project_path)

        if not source.exists():
            return {"error": f"Project not found: {project_path}"}

        # Generate template ID
        template_id = template_name.lower().replace(" ", "_")

        # Copy project to templates
        dest = self.templates_dir / f"{template_id}.blend"

        try:
            shutil.copy2(source, dest)

            # Create template configuration
            config = {
                "name": template_name,
                "description": description,
                "settings": {
                    "engine": "CYCLES",
                    "samples": 128,
                    "resolution": [1920, 1080],
                    "fps": 24,
                },
                "custom": True,
                "source_project": source.name,
            }

            # Save configuration
            config_file = self.templates_dir / f"{template_id}.json"
            config_file.write_text(json.dumps(config, indent=2))

            # Add to templates dictionary
            self.templates[template_id] = config

            return {
                "success": True,
                "template_id": template_id,
                "template_path": str(dest),
                "message": f"Template '{template_name}' created successfully",
            }

        except Exception as e:
            logger.error(f"Failed to save template: {e}")
            return {"error": str(e)}

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """Delete a custom template.

        Args:
            template_id: Template to delete

        Returns:
            Deletion result
        """
        # Don't allow deletion of built-in templates
        if (
            template_id in self.templates
            and isinstance(self.templates[template_id], dict)
            and not self.templates[template_id].get("custom", False)  # type: ignore
        ):
            return {"error": "Cannot delete built-in template"}

        # Remove files
        template_blend = self.templates_dir / f"{template_id}.blend"
        template_json = self.templates_dir / f"{template_id}.json"

        removed = False

        if template_blend.exists():
            template_blend.unlink()
            removed = True

        if template_json.exists():
            template_json.unlink()
            removed = True

        # Remove from dictionary
        if template_id in self.templates:
            del self.templates[template_id]
            removed = True

        if removed:
            return {"success": True, "message": f"Template '{template_id}' deleted"}
        else:
            return {"error": f"Template '{template_id}' not found"}
