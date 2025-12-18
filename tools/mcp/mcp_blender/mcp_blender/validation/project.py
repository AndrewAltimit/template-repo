"""Project validator.

Validates project creation parameters, template selection,
and project settings.
"""

import re
from typing import Any, Dict, Optional, Set

from .base import BaseValidator, ValidationResult


class ProjectValidator(BaseValidator):
    """Validator for project creation and settings.

    Validates project names, template selection, and configuration
    to ensure valid Blender project creation.
    """

    # Valid templates
    VALID_TEMPLATES: Set[str] = {
        "empty",
        "basic_scene",
        "studio_lighting",
        "procedural",
        "animation",
        "physics",
        "architectural",
        "product",
        "vfx",
        "game_asset",
        "sculpting",
    }

    # Valid render engines
    VALID_ENGINES: Set[str] = {
        "CYCLES",
        "BLENDER_EEVEE",
        "BLENDER_EEVEE_NEXT",
        "BLENDER_WORKBENCH",
        "EEVEE",
        "WORKBENCH",
    }

    # Project name constraints
    MAX_PROJECT_NAME_LENGTH: int = 255
    PROJECT_NAME_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9_\-][a-zA-Z0-9_\-\s]*$")

    # Reserved names that cannot be used
    RESERVED_NAMES: Set[str] = {
        "con",
        "prn",
        "aux",
        "nul",  # Windows reserved
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate project creation parameters.

        Args:
            data: Dictionary containing project parameters.

        Returns:
            ValidationResult with any errors found.
        """
        self.reset()

        self._validate_name(data.get("name"))
        self._validate_template(data.get("template"))
        self._validate_settings(data.get("settings"))

        return self.get_result()

    def _validate_name(self, name: Optional[str]) -> None:
        """Validate project name."""
        if name is None:
            self.add_error("Project name is required")
            return

        if not isinstance(name, str):
            self.add_error(f"Project name must be string, got {type(name).__name__}")
            return

        # Check length
        if len(name) == 0:
            self.add_error("Project name cannot be empty")
            return

        if len(name) > self.MAX_PROJECT_NAME_LENGTH:
            self.add_error(f"Project name exceeds maximum length ({len(name)} > {self.MAX_PROJECT_NAME_LENGTH})")
            return

        # Check for reserved names
        if name.lower() in self.RESERVED_NAMES:
            self.add_error(f"'{name}' is a reserved name and cannot be used")
            return

        # Check pattern
        if not self.PROJECT_NAME_PATTERN.match(name):
            self.add_error(
                f"Invalid project name: '{name}'. "
                "Must start with letter, number, underscore, or hyphen, "
                "and contain only letters, numbers, underscores, hyphens, or spaces"
            )

        # Warn about spaces
        if " " in name:
            self.add_warning("Project name contains spaces. Consider using underscores or hyphens for better compatibility")

    def _validate_template(self, template: Optional[str]) -> None:
        """Validate template selection."""
        if template is None:
            return  # Optional, defaults to 'basic_scene'

        if not isinstance(template, str):
            self.add_error(f"Template must be string, got {type(template).__name__}")
            return

        template_lower = template.lower()
        if template_lower not in self.VALID_TEMPLATES:
            valid_list = ", ".join(sorted(self.VALID_TEMPLATES))
            self.add_error(f"Invalid template: '{template}'. Valid options: {valid_list}")

    def _validate_settings(self, settings: Optional[Dict[str, Any]]) -> None:
        """Validate project settings."""
        if settings is None:
            return  # Optional

        if not isinstance(settings, dict):
            self.add_error(f"Settings must be dictionary, got {type(settings).__name__}")
            return

        # Validate resolution if present
        if "resolution" in settings:
            self._validate_resolution(settings["resolution"])

        # Validate FPS if present
        if "fps" in settings:
            self._validate_fps(settings["fps"])

        # Validate engine if present
        if "engine" in settings:
            self._validate_engine(settings["engine"])

    def _validate_resolution(self, resolution: Any) -> None:
        """Validate resolution setting."""
        if not isinstance(resolution, (list, tuple)):
            self.add_error("Resolution must be [width, height] list")
            return

        if len(resolution) != 2:
            self.add_error(f"Resolution must have 2 values, got {len(resolution)}")
            return

        width, height = resolution
        if not isinstance(width, int) or not isinstance(height, int):
            self.add_error("Resolution width and height must be integers")
            return

        if width < 1 or height < 1:
            self.add_error("Resolution dimensions must be positive integers")
        elif width > 65536 or height > 65536:
            self.add_error("Resolution dimensions exceed maximum (65536)")

    def _validate_fps(self, fps: Any) -> None:
        """Validate FPS setting."""
        if not isinstance(fps, (int, float)):
            self.add_error(f"FPS must be number, got {type(fps).__name__}")
            return

        if fps < 1:
            self.add_error("FPS must be >= 1")
        elif fps > 240:
            self.add_error("FPS exceeds maximum (240)")

    def _validate_engine(self, engine: Any) -> None:
        """Validate render engine setting."""
        if not isinstance(engine, str):
            self.add_error(f"Engine must be string, got {type(engine).__name__}")
            return

        engine_upper = engine.upper()
        if engine_upper not in self.VALID_ENGINES:
            valid_list = ", ".join(sorted(self.VALID_ENGINES))
            self.add_error(f"Invalid engine: '{engine}'. Valid options: {valid_list}")
