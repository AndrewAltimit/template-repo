"""Custom JSON encoder for numpy types and versioned output support."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional

import numpy as np

# Schema version for CLI JSON outputs
# Increment when making breaking changes to output format
SCHEMA_VERSION = "1.0.0"


def create_versioned_output(
    data: Any,
    schema_type: str,
    version: str = SCHEMA_VERSION,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a versioned JSON output structure.

    This wraps data in a standardized envelope with version information
    for downstream tooling compatibility.

    Args:
        data: The actual data payload
        schema_type: Type of output (e.g., "evaluation_results", "detection_results")
        version: Schema version string (semver format)
        metadata: Optional additional metadata

    Returns:
        Versioned output dictionary

    Example:
        >>> results = {"accuracy": 0.95, "f1": 0.92}
        >>> output = create_versioned_output(results, "evaluation_results")
        >>> # output = {
        >>> #     "schema_version": "1.0.0",
        >>> #     "schema_type": "evaluation_results",
        >>> #     "generated_at": "2024-01-07T12:00:00Z",
        >>> #     "data": {"accuracy": 0.95, "f1": 0.92}
        >>> # }
    """
    output: Dict[str, Any] = {
        "schema_version": version,
        "schema_type": schema_type,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "data": data,
    }

    if metadata:
        output["metadata"] = metadata

    return output


def dumps_versioned(
    data: Any,
    schema_type: str,
    indent: int = 2,
    version: str = SCHEMA_VERSION,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Serialize data to versioned JSON string.

    Args:
        data: Data to serialize
        schema_type: Type of output schema
        indent: JSON indentation level
        version: Schema version
        metadata: Optional metadata

    Returns:
        Versioned JSON string
    """
    versioned = create_versioned_output(data, schema_type, version, metadata)
    return json.dumps(versioned, cls=NumpyJSONEncoder, indent=indent, default=str)


class NumpyJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for numpy types and domain objects.

    Converts numpy types to their Python native equivalents for JSON serialization.
    This encoder handles:
    - numpy integers -> Python int
    - numpy floats -> Python float
    - numpy booleans -> Python bool
    - numpy arrays -> Python list
    - datetime objects -> ISO format strings
    - Objects with to_dict() method -> dict (e.g., EvaluationResult)

    Example:
        >>> import numpy as np
        >>> import json
        >>> from sleeper_agents.utils.json_encoder import NumpyJSONEncoder
        >>>
        >>> data = {
        ...     'bool_val': np.bool_(True),
        ...     'int_val': np.int64(42),
        ...     'float_val': np.float32(3.14),
        ...     'array': np.array([1, 2, 3])
        ... }
        >>> json.dumps(data, cls=NumpyJSONEncoder)
    """

    def default(self, o: Any) -> Any:
        """Convert numpy types and domain objects to Python native types.

        Args:
            o: Object to be serialized

        Returns:
            Python native type equivalent

        Raises:
            TypeError: If the object is not JSON serializable
        """
        # NumPy types
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bool_):
            return bool(o)

        # Datetime objects
        if isinstance(o, datetime):
            return o.isoformat()

        # Domain objects with to_dict() method (e.g., EvaluationResult)
        if hasattr(o, "to_dict") and callable(getattr(o, "to_dict")):
            return o.to_dict()

        # Let the base class raise the TypeError
        return super().default(o)
