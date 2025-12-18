"""Render settings validator.

Validates render configuration including engine selection, sample counts,
resolution, output format, and quality settings.
"""

from typing import Any, Dict, List, Optional, Set

from .base import BaseValidator, ValidationResult


class RenderValidator(BaseValidator):
    """Validator for render settings.

    Validates render engine, samples, resolution, and output format
    to ensure valid Blender configurations.
    """

    # Valid render engines (Blender 4.0+ uses BLENDER_ prefix)
    VALID_ENGINES: Set[str] = {
        "CYCLES",
        "BLENDER_EEVEE",
        "BLENDER_EEVEE_NEXT",
        "BLENDER_WORKBENCH",
        # Legacy names (mapped in Blender)
        "EEVEE",
        "WORKBENCH",
    }

    # Valid output formats
    VALID_FORMATS: Set[str] = {
        "PNG",
        "JPEG",
        "BMP",
        "TIFF",
        "OPEN_EXR",
        "OPEN_EXR_MULTILAYER",
        "HDR",
        "CINEON",
        "DPX",
        "WEBP",
        # Animation formats
        "AVI_JPEG",
        "AVI_RAW",
        "FFMPEG",
    }

    # Common video containers when using FFMPEG
    VALID_CONTAINERS: Set[str] = {
        "MP4",
        "MKV",
        "WEBM",
        "OGG",
        "AVI",
        "MOV",
    }

    # Sample limits
    MIN_SAMPLES: int = 1
    MAX_SAMPLES: int = 65536

    # Resolution limits
    MIN_RESOLUTION: int = 1
    MAX_RESOLUTION: int = 65536

    # Frame rate limits
    MIN_FPS: int = 1
    MAX_FPS: int = 240

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate render settings.

        Args:
            data: Dictionary containing render settings.

        Returns:
            ValidationResult with any errors found.
        """
        self.reset()
        settings = data.get("settings", {})

        self._validate_engine(settings.get("engine"))
        self._validate_samples(settings.get("samples"))
        self._validate_resolution(settings.get("resolution"))
        self._validate_format(settings.get("format"))
        self._validate_fps(settings.get("fps"))
        self._validate_frame_range(settings.get("frame"), settings.get("start_frame"), settings.get("end_frame"))

        return self.get_result()

    def _validate_engine(self, engine: Optional[str]) -> None:
        """Validate render engine."""
        if engine is None:
            return  # Optional, defaults to CYCLES

        if not isinstance(engine, str):
            self.add_error(f"Engine must be string, got {type(engine).__name__}")
            return

        engine_upper = engine.upper()
        if engine_upper not in self.VALID_ENGINES:
            valid_list = ", ".join(sorted(self.VALID_ENGINES))
            self.add_error(f"Invalid render engine: '{engine}'. Valid options: {valid_list}")

    def _validate_samples(self, samples: Optional[int]) -> None:
        """Validate sample count."""
        if samples is None:
            return  # Optional

        if not isinstance(samples, int):
            self.add_error(f"Samples must be integer, got {type(samples).__name__}")
            return

        if samples < self.MIN_SAMPLES:
            self.add_error(f"Samples must be >= {self.MIN_SAMPLES}, got {samples}")
        elif samples > self.MAX_SAMPLES:
            self.add_error(f"Samples must be <= {self.MAX_SAMPLES}, got {samples}")
        elif samples > 4096:
            self.add_warning(f"High sample count ({samples}) may result in very long render times")

    def _validate_resolution(
        self,
        resolution: Optional[List[int]],
    ) -> None:
        """Validate resolution."""
        if resolution is None:
            return  # Optional

        if not isinstance(resolution, (list, tuple)):
            self.add_error("Resolution must be [width, height] list")
            return

        if len(resolution) != 2:
            self.add_error(f"Resolution must have 2 values [width, height], got {len(resolution)}")
            return

        width, height = resolution

        if not isinstance(width, int) or not isinstance(height, int):
            self.add_error("Resolution width and height must be integers")
            return

        if width < self.MIN_RESOLUTION or height < self.MIN_RESOLUTION:
            self.add_error(f"Resolution dimensions must be >= {self.MIN_RESOLUTION}, got [{width}, {height}]")
        elif width > self.MAX_RESOLUTION or height > self.MAX_RESOLUTION:
            self.add_error(f"Resolution dimensions must be <= {self.MAX_RESOLUTION}, got [{width}, {height}]")

        # Warn about very high resolutions
        if width * height > 33177600:  # > 8K
            self.add_warning(f"Very high resolution ({width}x{height}) may require significant memory and render time")

    def _validate_format(self, format_str: Optional[str]) -> None:
        """Validate output format."""
        if format_str is None:
            return  # Optional

        if not isinstance(format_str, str):
            self.add_error(f"Format must be string, got {type(format_str).__name__}")
            return

        format_upper = format_str.upper()

        # Check if it's a valid format or common alias
        if format_upper not in self.VALID_FORMATS:
            # Check common aliases
            aliases = {
                "EXR": "OPEN_EXR",
                "EXRMULTI": "OPEN_EXR_MULTILAYER",
                "MP4": "FFMPEG",
                "MKV": "FFMPEG",
                "WEBM": "FFMPEG",
            }
            if format_upper not in aliases:
                valid_list = ", ".join(sorted(self.VALID_FORMATS))
                self.add_error(f"Invalid format: '{format_str}'. Valid options: {valid_list}")

    def _validate_fps(self, fps: Optional[int]) -> None:
        """Validate frame rate."""
        if fps is None:
            return  # Optional

        if not isinstance(fps, (int, float)):
            self.add_error(f"FPS must be number, got {type(fps).__name__}")
            return

        if fps < self.MIN_FPS:
            self.add_error(f"FPS must be >= {self.MIN_FPS}, got {fps}")
        elif fps > self.MAX_FPS:
            self.add_error(f"FPS must be <= {self.MAX_FPS}, got {fps}")

    def _validate_frame_range(
        self,
        frame: Optional[int],
        start_frame: Optional[int],
        end_frame: Optional[int],
    ) -> None:
        """Validate frame or frame range."""
        # Single frame
        if frame is not None:
            if not isinstance(frame, int):
                self.add_error(f"Frame must be integer, got {type(frame).__name__}")
            elif frame < 0:
                self.add_error(f"Frame must be >= 0, got {frame}")

        # Frame range
        if start_frame is not None and end_frame is not None:
            if not isinstance(start_frame, int):
                self.add_error(f"Start frame must be integer, got {type(start_frame).__name__}")
            if not isinstance(end_frame, int):
                self.add_error(f"End frame must be integer, got {type(end_frame).__name__}")

            if isinstance(start_frame, int) and isinstance(end_frame, int):
                if start_frame < 0:
                    self.add_error(f"Start frame must be >= 0, got {start_frame}")
                if end_frame < start_frame:
                    self.add_error(f"End frame ({end_frame}) must be >= start frame ({start_frame})")
                elif end_frame - start_frame > 10000:
                    self.add_warning(
                        f"Large frame range ({end_frame - start_frame + 1} frames) may result in very long render times"
                    )

    def validate_settings(self, settings: Dict[str, Any]) -> List[str]:
        """Validate render settings and return list of errors.

        Convenience method that returns just the error list.

        Args:
            settings: Dictionary of render settings.

        Returns:
            List of error messages (empty if valid).
        """
        result = self.validate({"settings": settings})
        return result.errors
