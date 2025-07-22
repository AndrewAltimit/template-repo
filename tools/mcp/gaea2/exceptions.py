"""
Custom exception types for Gaea2 MCP operations.

This module defines specific exception classes for different error scenarios
in Gaea2 operations, improving error handling and debugging capabilities.
"""

from typing import Any, Optional


class Gaea2Exception(Exception):
    """Base exception class for all Gaea2-related errors"""

    pass


class Gaea2ValidationError(Gaea2Exception):
    """Raised when validation of Gaea2 data fails"""

    def __init__(
        self,
        message: str,
        node_id: Optional[int] = None,
        property_name: Optional[str] = None,
    ):
        self.node_id = node_id
        self.property_name = property_name
        super().__init__(message)


class Gaea2NodeTypeError(Gaea2ValidationError):
    """Raised when an invalid node type is encountered"""

    def __init__(self, node_type: str, node_id: Optional[int] = None):
        self.node_type = node_type
        message = f"Invalid node type: {node_type}"
        super().__init__(message, node_id=node_id)


class Gaea2PropertyError(Gaea2ValidationError):
    """Raised when a property value is invalid"""

    def __init__(
        self,
        property_name: str,
        value: Any,
        expected_type: str,
        node_id: Optional[int] = None,
    ):
        self.value = value
        self.expected_type = expected_type
        message = f"Invalid value for property '{property_name}': {value} (expected {expected_type})"
        super().__init__(message, node_id=node_id, property_name=property_name)


class Gaea2ConnectionError(Gaea2Exception):
    """Raised when connection validation fails"""

    def __init__(
        self,
        message: str,
        from_node: Optional[int] = None,
        to_node: Optional[int] = None,
        from_port: Optional[str] = None,
        to_port: Optional[str] = None,
    ):
        self.from_node = from_node
        self.to_node = to_node
        self.from_port = from_port
        self.to_port = to_port
        super().__init__(message)


class Gaea2StructureError(Gaea2Exception):
    """Raised when project structure is invalid"""

    def __init__(self, message: str, missing_key: Optional[str] = None):
        self.missing_key = missing_key
        super().__init__(message)


class Gaea2FileError(Gaea2Exception):
    """Raised when file operations fail"""

    def __init__(self, message: str, file_path: Optional[str] = None):
        self.file_path = file_path
        super().__init__(message)


class Gaea2ParseError(Gaea2Exception):
    """Raised when parsing Gaea2 project data fails"""

    def __init__(self, message: str, line_number: Optional[int] = None):
        self.line_number = line_number
        super().__init__(message)


class Gaea2RepairError(Gaea2Exception):
    """Raised when project repair operations fail"""

    def __init__(self, message: str, repair_type: Optional[str] = None):
        self.repair_type = repair_type
        super().__init__(message)


class Gaea2OptimizationError(Gaea2Exception):
    """Raised when optimization operations fail"""

    def __init__(self, message: str, optimization_type: Optional[str] = None):
        self.optimization_type = optimization_type
        super().__init__(message)


class Gaea2RuntimeError(Gaea2Exception):
    """Raised when Gaea2 CLI operations fail"""

    def __init__(
        self,
        message: str,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(message)


class Gaea2TimeoutError(Gaea2RuntimeError):
    """Raised when Gaea2 operations timeout"""

    def __init__(self, message: str, timeout_seconds: Optional[int] = None):
        self.timeout_seconds = timeout_seconds
        super().__init__(message)
