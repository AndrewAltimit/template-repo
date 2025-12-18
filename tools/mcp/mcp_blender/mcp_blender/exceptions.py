"""Custom exception hierarchy for Blender MCP operations.

This module provides a comprehensive exception hierarchy for error handling
across all Blender MCP operations. Each exception type captures relevant
context information for debugging and error reporting.

Exception Hierarchy:
    BlenderError (base)
    ├── BlenderValidationError - Input validation failures
    ├── BlenderExecutionError - Blender subprocess failures
    ├── BlenderTimeoutError - Operation timeout
    ├── BlenderAssetError - Asset not found or invalid
    ├── BlenderProjectError - Project-level errors
    ├── BlenderRenderError - Rendering failures
    ├── BlenderPhysicsError - Physics simulation errors
    └── BlenderAnimationError - Animation setup errors
"""

from typing import Any, Dict, List, Optional


class BlenderError(Exception):
    """Base exception for all Blender MCP operations.

    All Blender-specific exceptions inherit from this class, allowing
    for broad exception catching when needed.

    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional context.
    """

    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class BlenderValidationError(BlenderError):
    """Raised when input validation fails.

    Use this exception for parameter validation errors, schema violations,
    and constraint checks before operations execute.

    Attributes:
        field: Name of the field that failed validation.
        value: The invalid value that was provided.
        constraint: Description of the validation constraint violated.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        constraint: Optional[str] = None,
    ):
        self.field = field
        self.value = value
        self.constraint = constraint
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        if constraint:
            details["constraint"] = constraint
        super().__init__(message, details)


class BlenderExecutionError(BlenderError):
    """Raised when Blender subprocess execution fails.

    This exception captures information about Blender subprocess failures,
    including exit codes and stderr output for debugging.

    Attributes:
        exit_code: Process exit code (non-zero indicates failure).
        stderr: Standard error output from the subprocess.
        stdout: Standard output from the subprocess.
        command: The command that was executed.
    """

    def __init__(
        self,
        message: str,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
        stdout: Optional[str] = None,
        command: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout
        self.command = command
        details: Dict[str, Any] = {}
        if exit_code is not None:
            details["exit_code"] = exit_code
        if stderr:
            # Truncate long stderr output
            details["stderr"] = stderr[:1000] if len(stderr) > 1000 else stderr
        if command:
            details["command"] = command
        super().__init__(message, details)


class BlenderTimeoutError(BlenderError):
    """Raised when an operation exceeds its timeout.

    Use this exception for operations that take too long, including
    rendering, simulation baking, and export operations.

    Attributes:
        timeout_seconds: The timeout duration that was exceeded.
        operation: Name of the operation that timed out.
        elapsed_seconds: Actual time elapsed before timeout.
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        operation: Optional[str] = None,
        elapsed_seconds: Optional[float] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        self.elapsed_seconds = elapsed_seconds
        details: Dict[str, Any] = {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        if operation:
            details["operation"] = operation
        if elapsed_seconds is not None:
            details["elapsed_seconds"] = elapsed_seconds
        super().__init__(message, details)


class BlenderAssetError(BlenderError):
    """Raised when an asset is not found or invalid.

    Use this exception for missing textures, models, HDRIs, or other
    external assets required by operations.

    Attributes:
        asset_path: Path to the missing or invalid asset.
        asset_type: Type of asset (texture, model, hdri, etc.).
        expected_formats: List of valid formats if format mismatch.
    """

    def __init__(
        self,
        message: str,
        asset_path: Optional[str] = None,
        asset_type: Optional[str] = None,
        expected_formats: Optional[List[str]] = None,
    ):
        self.asset_path = asset_path
        self.asset_type = asset_type
        self.expected_formats = expected_formats
        details: Dict[str, Any] = {}
        if asset_path:
            details["asset_path"] = asset_path
        if asset_type:
            details["asset_type"] = asset_type
        if expected_formats:
            details["expected_formats"] = expected_formats
        super().__init__(message, details)


class BlenderProjectError(BlenderError):
    """Raised for project-level errors.

    Use this exception for errors related to .blend file operations,
    project creation, loading, or saving.

    Attributes:
        project_path: Path to the project file.
        operation: The project operation that failed.
    """

    def __init__(
        self,
        message: str,
        project_path: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        self.project_path = project_path
        self.operation = operation
        details = {}
        if project_path:
            details["project_path"] = project_path
        if operation:
            details["operation"] = operation
        super().__init__(message, details)


class BlenderRenderError(BlenderError):
    """Raised when rendering fails.

    Use this exception for render-specific errors including GPU failures,
    memory exhaustion, and output format issues.

    Attributes:
        job_id: ID of the render job that failed.
        engine: Render engine being used (CYCLES, EEVEE, etc.).
        frame: Frame number being rendered when error occurred.
        gpu_error: Whether the error is GPU-related.
    """

    def __init__(
        self,
        message: str,
        job_id: Optional[str] = None,
        engine: Optional[str] = None,
        frame: Optional[int] = None,
        gpu_error: bool = False,
    ):
        self.job_id = job_id
        self.engine = engine
        self.frame = frame
        self.gpu_error = gpu_error
        details: Dict[str, Any] = {}
        if job_id:
            details["job_id"] = job_id
        if engine:
            details["engine"] = engine
        if frame is not None:
            details["frame"] = frame
        if gpu_error:
            details["gpu_error"] = True
        super().__init__(message, details)


class BlenderPhysicsError(BlenderError):
    """Raised when physics simulation fails.

    Use this exception for physics-related errors including baking failures,
    invalid settings, and simulation instabilities.

    Attributes:
        object_name: Name of the object with physics issues.
        physics_type: Type of physics (rigid_body, soft_body, cloth, fluid).
        frame: Frame where simulation failed.
    """

    def __init__(
        self,
        message: str,
        object_name: Optional[str] = None,
        physics_type: Optional[str] = None,
        frame: Optional[int] = None,
    ):
        self.object_name = object_name
        self.physics_type = physics_type
        self.frame = frame
        details: Dict[str, Any] = {}
        if object_name:
            details["object_name"] = object_name
        if physics_type:
            details["physics_type"] = physics_type
        if frame is not None:
            details["frame"] = frame
        super().__init__(message, details)


class BlenderAnimationError(BlenderError):
    """Raised when animation setup or playback fails.

    Use this exception for keyframe errors, constraint issues,
    and NLA-related problems.

    Attributes:
        object_name: Name of the animated object.
        frame: Frame where error occurred.
        action_name: Name of the action/animation clip.
    """

    def __init__(
        self,
        message: str,
        object_name: Optional[str] = None,
        frame: Optional[int] = None,
        action_name: Optional[str] = None,
    ):
        self.object_name = object_name
        self.frame = frame
        self.action_name = action_name
        details: Dict[str, Any] = {}
        if object_name:
            details["object_name"] = object_name
        if frame is not None:
            details["frame"] = frame
        if action_name:
            details["action_name"] = action_name
        super().__init__(message, details)


class BlenderPathError(BlenderError):
    """Raised when path validation fails.

    Use this exception for path traversal attempts, invalid paths,
    and permission issues.

    Attributes:
        path: The problematic path.
        reason: Specific reason for rejection.
        allowed_base: The allowed base directory.
    """

    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        reason: Optional[str] = None,
        allowed_base: Optional[str] = None,
    ):
        self.path = path
        self.reason = reason
        self.allowed_base = allowed_base
        details = {}
        if path:
            details["path"] = path
        if reason:
            details["reason"] = reason
        if allowed_base:
            details["allowed_base"] = allowed_base
        super().__init__(message, details)
