"""Asset validator.

Validates asset paths, file formats, and asset-related operations
including imports, exports, and texture handling.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import BaseValidator, ValidationResult


class AssetValidator(BaseValidator):
    """Validator for asset paths and formats.

    Validates file paths, supported formats, and asset availability
    for import/export operations.
    """

    # Supported import formats
    IMPORT_FORMATS: Set[str] = {
        # 3D Models
        "FBX",
        "OBJ",
        "GLTF",
        "GLB",
        "STL",
        "PLY",
        "DAE",  # Collada
        "ABC",  # Alembic
        "USD",
        "USDA",
        "USDC",
        "USDZ",
        "X3D",
        "WRL",
        "3DS",
        "BVH",
    }

    # Supported export formats
    EXPORT_FORMATS: Set[str] = {
        "FBX",
        "OBJ",
        "GLTF",
        "GLB",
        "STL",
        "PLY",
        "DAE",
        "ABC",
        "USD",
        "USDA",
        "USDC",
        "USDZ",
        "X3D",
    }

    # Supported image formats (for textures)
    IMAGE_FORMATS: Set[str] = {
        "PNG",
        "JPG",
        "JPEG",
        "BMP",
        "TIFF",
        "TIF",
        "TGA",
        "EXR",
        "HDR",
        "WEBP",
        "PSD",
    }

    # HDRI formats
    HDRI_FORMATS: Set[str] = {
        "HDR",
        "EXR",
    }

    # Allowed base directories (for path validation)
    ALLOWED_BASES: List[str] = [
        "/app/projects",
        "/app/assets",
        "/app/outputs",
        "/app/templates",
    ]

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate asset parameters.

        Args:
            data: Dictionary containing asset parameters.

        Returns:
            ValidationResult with any errors found.
        """
        self.reset()

        # Validate based on operation type
        operation = data.get("operation", "import")

        if operation == "import":
            self._validate_import(data)
        elif operation == "export":
            self._validate_export(data)
        elif operation == "texture":
            self._validate_texture(data)
        else:
            self._validate_path(data.get("path"), "path")

        return self.get_result()

    def _validate_import(self, data: Dict[str, Any]) -> None:
        """Validate import operation parameters."""
        model_path = data.get("model_path")
        file_format = data.get("format")

        # Validate path
        if model_path:
            self._validate_path(model_path, "model_path")
            self._validate_path_security(model_path)

            # Infer format from extension if not provided
            if not file_format:
                ext = self._get_extension(model_path)
                if ext:
                    file_format = ext

        # Validate format
        if file_format:
            self._validate_format(file_format, self.IMPORT_FORMATS, "import format")

    def _validate_export(self, data: Dict[str, Any]) -> None:
        """Validate export operation parameters."""
        output_path = data.get("output_path")
        file_format = data.get("format")

        # Validate output path
        if output_path:
            self._validate_path_security(output_path)

        # Validate format
        if file_format:
            self._validate_format(file_format, self.EXPORT_FORMATS, "export format")
        else:
            self.add_warning("No export format specified. Will attempt to infer from filename or use default (GLTF)")

    def _validate_texture(self, data: Dict[str, Any]) -> None:
        """Validate texture path and format."""
        texture_path = data.get("texture_path")

        if texture_path:
            self._validate_path(texture_path, "texture_path")
            self._validate_path_security(texture_path)

            # Check format
            ext = self._get_extension(texture_path)
            if ext and ext.upper() not in self.IMAGE_FORMATS:
                valid_list = ", ".join(sorted(self.IMAGE_FORMATS))
                self.add_error(f"Invalid texture format: '.{ext}'. Valid formats: {valid_list}")

    def _validate_path(self, path: Optional[str], field_name: str) -> bool:
        """Validate that a path is provided and non-empty."""
        if path is None:
            self.add_error(f"{field_name} is required")
            return False

        if not isinstance(path, str):
            self.add_error(f"{field_name} must be string, got {type(path).__name__}")
            return False

        if not path.strip():
            self.add_error(f"{field_name} cannot be empty")
            return False

        return True

    def _validate_path_security(self, path: str) -> bool:
        """Validate path against security concerns.

        Checks for path traversal attempts and ensures path
        is within allowed directories.
        """
        # Check for obvious traversal attempts
        if ".." in path:
            self.add_error(f"Path traversal not allowed: '{path}' contains '..'")
            return False

        # Normalize path
        try:
            normalized = os.path.normpath(path)
        except (ValueError, OSError) as e:
            self.add_error(f"Invalid path: {e}")
            return False

        # Check if absolute path is within allowed directories
        if os.path.isabs(path):
            in_allowed = any(normalized.startswith(base) for base in self.ALLOWED_BASES)
            if not in_allowed:
                bases = ", ".join(self.ALLOWED_BASES)
                self.add_error(f"Path '{path}' is outside allowed directories. Must be within: {bases}")
                return False

        return True

    def _validate_format(
        self,
        file_format: str,
        valid_formats: Set[str],
        format_type: str,
    ) -> bool:
        """Validate file format against set of valid formats."""
        if not isinstance(file_format, str):
            self.add_error(f"Format must be string, got {type(file_format).__name__}")
            return False

        format_upper = file_format.upper().lstrip(".")

        if format_upper not in valid_formats:
            valid_list = ", ".join(sorted(valid_formats))
            self.add_error(f"Invalid {format_type}: '{file_format}'. Valid options: {valid_list}")
            return False

        return True

    def _get_extension(self, path: str) -> Optional[str]:
        """Extract file extension from path."""
        try:
            ext = Path(path).suffix
            if ext:
                return ext.lstrip(".")
        except (ValueError, OSError):
            pass
        return None

    def validate_hdri_path(self, path: str) -> ValidationResult:
        """Validate HDRI file path specifically.

        Args:
            path: Path to HDRI file.

        Returns:
            ValidationResult with any errors found.
        """
        self.reset()

        if not self._validate_path(path, "hdri_path"):
            return self.get_result()

        self._validate_path_security(path)

        # Check format
        ext = self._get_extension(path)
        if ext and ext.upper() not in self.HDRI_FORMATS:
            valid_list = ", ".join(sorted(self.HDRI_FORMATS))
            self.add_error(f"Invalid HDRI format: '.{ext}'. Valid formats: {valid_list}")

        return self.get_result()

    def validate_model_path(
        self,
        path: str,
        for_import: bool = True,
    ) -> ValidationResult:
        """Validate 3D model file path.

        Args:
            path: Path to 3D model file.
            for_import: Whether this is for import (True) or export (False).

        Returns:
            ValidationResult with any errors found.
        """
        self.reset()

        if not self._validate_path(path, "model_path"):
            return self.get_result()

        self._validate_path_security(path)

        # Check format
        ext = self._get_extension(path)
        if ext:
            valid_formats = self.IMPORT_FORMATS if for_import else self.EXPORT_FORMATS
            format_type = "import" if for_import else "export"
            if ext.upper() not in valid_formats:
                valid_list = ", ".join(sorted(valid_formats))
                self.add_error(f"Invalid {format_type} format: '.{ext}'. Valid formats: {valid_list}")

        return self.get_result()
