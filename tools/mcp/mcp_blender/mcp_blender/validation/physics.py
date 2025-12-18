"""Physics settings validator.

Validates physics simulation parameters including rigid body settings,
soft body settings, cloth simulation, and fluid dynamics.
"""

from typing import Any, Dict, Optional, Set

from .base import BaseValidator, ValidationResult


class PhysicsValidator(BaseValidator):
    """Validator for physics simulation settings.

    Validates physics type, mass, friction, bounce, and other
    simulation parameters for Blender physics.
    """

    # Valid physics types
    VALID_PHYSICS_TYPES: Set[str] = {
        "rigid_body",
        "soft_body",
        "cloth",
        "fluid",
        "collision",
        "force_field",
    }

    # Valid rigid body types
    VALID_RIGID_BODY_TYPES: Set[str] = {
        "ACTIVE",
        "PASSIVE",
    }

    # Valid collision shapes
    VALID_COLLISION_SHAPES: Set[str] = {
        "BOX",
        "SPHERE",
        "CAPSULE",
        "CYLINDER",
        "CONE",
        "CONVEX_HULL",
        "MESH",
        "COMPOUND",
    }

    # Valid fluid types
    VALID_FLUID_TYPES: Set[str] = {
        "DOMAIN",
        "FLOW",
        "EFFECTOR",
    }

    # Physical constraints
    MIN_MASS: float = 0.0
    MAX_MASS: float = 100000.0
    MIN_FRICTION: float = 0.0
    MAX_FRICTION: float = 1.0
    MIN_BOUNCE: float = 0.0
    MAX_BOUNCE: float = 1.0

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate physics settings.

        Args:
            data: Dictionary containing physics parameters.

        Returns:
            ValidationResult with any errors found.
        """
        self.reset()

        physics_type = data.get("physics_type")
        settings = data.get("settings", {})

        self._validate_physics_type(physics_type)

        if physics_type == "rigid_body":
            self._validate_rigid_body_settings(settings)
        elif physics_type == "soft_body":
            self._validate_soft_body_settings(settings)
        elif physics_type == "cloth":
            self._validate_cloth_settings(settings)
        elif physics_type == "fluid":
            self._validate_fluid_settings(settings)

        return self.get_result()

    def _validate_physics_type(self, physics_type: Optional[str]) -> None:
        """Validate physics type."""
        if physics_type is None:
            self.add_error("Physics type is required")
            return

        if not isinstance(physics_type, str):
            self.add_error(f"Physics type must be string, got {type(physics_type).__name__}")
            return

        if physics_type.lower() not in self.VALID_PHYSICS_TYPES:
            valid_list = ", ".join(sorted(self.VALID_PHYSICS_TYPES))
            self.add_error(f"Invalid physics type: '{physics_type}'. Valid options: {valid_list}")

    def _validate_rigid_body_settings(self, settings: Dict[str, Any]) -> None:
        """Validate rigid body physics settings."""
        # Validate mass
        if "mass" in settings:
            mass = settings["mass"]
            if not isinstance(mass, (int, float)):
                self.add_error(f"Mass must be number, got {type(mass).__name__}")
            elif mass < self.MIN_MASS:
                self.add_error(f"Mass must be >= {self.MIN_MASS}, got {mass}")
            elif mass > self.MAX_MASS:
                self.add_error(f"Mass must be <= {self.MAX_MASS}, got {mass}")
            elif mass == 0:
                self.add_warning("Mass of 0 makes object weightless")

        # Validate friction
        if "friction" in settings:
            friction = settings["friction"]
            if not isinstance(friction, (int, float)):
                self.add_error(f"Friction must be number, got {type(friction).__name__}")
            elif friction < self.MIN_FRICTION:
                self.add_error(f"Friction must be >= {self.MIN_FRICTION}, got {friction}")
            elif friction > self.MAX_FRICTION:
                self.add_error(f"Friction must be <= {self.MAX_FRICTION}, got {friction}")

        # Validate bounce (restitution)
        if "bounce" in settings:
            bounce = settings["bounce"]
            if not isinstance(bounce, (int, float)):
                self.add_error(f"Bounce must be number, got {type(bounce).__name__}")
            elif bounce < self.MIN_BOUNCE:
                self.add_error(f"Bounce must be >= {self.MIN_BOUNCE}, got {bounce}")
            elif bounce > self.MAX_BOUNCE:
                self.add_error(f"Bounce must be <= {self.MAX_BOUNCE}, got {bounce}")

        # Validate collision shape
        if "collision_shape" in settings:
            shape = settings["collision_shape"]
            if not isinstance(shape, str):
                self.add_error(f"Collision shape must be string, got {type(shape).__name__}")
            elif shape.upper() not in self.VALID_COLLISION_SHAPES:
                valid_list = ", ".join(sorted(self.VALID_COLLISION_SHAPES))
                self.add_error(f"Invalid collision shape: '{shape}'. Valid options: {valid_list}")
            elif shape.upper() == "MESH":
                self.add_warning("MESH collision shape is slow. Consider CONVEX_HULL for better performance")

        # Validate rigid body type
        if "rigid_body_type" in settings:
            rb_type = settings["rigid_body_type"]
            if not isinstance(rb_type, str):
                self.add_error(f"Rigid body type must be string, got {type(rb_type).__name__}")
            elif rb_type.upper() not in self.VALID_RIGID_BODY_TYPES:
                valid_list = ", ".join(sorted(self.VALID_RIGID_BODY_TYPES))
                self.add_error(f"Invalid rigid body type: '{rb_type}'. Valid options: {valid_list}")

    def _validate_soft_body_settings(self, settings: Dict[str, Any]) -> None:
        """Validate soft body physics settings."""
        # Validate goal settings
        if "goal" in settings:
            goal = settings["goal"]
            if not isinstance(goal, (int, float)):
                self.add_error(f"Goal must be number, got {type(goal).__name__}")
            elif goal < 0 or goal > 1:
                self.add_error(f"Goal must be between 0 and 1, got {goal}")

        # Validate stiffness
        if "stiffness" in settings:
            stiffness = settings["stiffness"]
            if not isinstance(stiffness, (int, float)):
                self.add_error(f"Stiffness must be number, got {type(stiffness).__name__}")
            elif stiffness < 0:
                self.add_error(f"Stiffness must be >= 0, got {stiffness}")

        # Validate damping
        if "damping" in settings:
            damping = settings["damping"]
            if not isinstance(damping, (int, float)):
                self.add_error(f"Damping must be number, got {type(damping).__name__}")
            elif damping < 0 or damping > 1:
                self.add_error(f"Damping must be between 0 and 1, got {damping}")

    def _validate_cloth_settings(self, settings: Dict[str, Any]) -> None:
        """Validate cloth simulation settings."""
        # Validate quality
        if "quality" in settings:
            quality = settings["quality"]
            if not isinstance(quality, int):
                self.add_error(f"Quality must be integer, got {type(quality).__name__}")
            elif quality < 1:
                self.add_error(f"Quality must be >= 1, got {quality}")
            elif quality > 80:
                self.add_warning(f"High quality ({quality}) may result in slow simulation")

        # Validate air damping
        if "air_damping" in settings:
            air = settings["air_damping"]
            if not isinstance(air, (int, float)):
                self.add_error(f"Air damping must be number, got {type(air).__name__}")
            elif air < 0:
                self.add_error(f"Air damping must be >= 0, got {air}")

    def _validate_fluid_settings(self, settings: Dict[str, Any]) -> None:
        """Validate fluid simulation settings."""
        # Validate fluid type
        if "fluid_type" in settings:
            fluid_type = settings["fluid_type"]
            if not isinstance(fluid_type, str):
                self.add_error(f"Fluid type must be string, got {type(fluid_type).__name__}")
            elif fluid_type.upper() not in self.VALID_FLUID_TYPES:
                valid_list = ", ".join(sorted(self.VALID_FLUID_TYPES))
                self.add_error(f"Invalid fluid type: '{fluid_type}'. Valid options: {valid_list}")

        # Validate resolution
        if "resolution" in settings:
            resolution = settings["resolution"]
            if not isinstance(resolution, int):
                self.add_error(f"Resolution must be integer, got {type(resolution).__name__}")
            elif resolution < 24:
                self.add_error(f"Resolution must be >= 24, got {resolution}")
            elif resolution > 512:
                self.add_warning(f"High resolution ({resolution}) may require significant memory and compute time")
