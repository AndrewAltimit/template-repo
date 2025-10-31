"""Custom JSON encoder for numpy types."""

import json
from typing import Any

import numpy as np


class NumpyJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for numpy types.

    Converts numpy types to their Python native equivalents for JSON serialization.
    This encoder handles:
    - numpy integers -> Python int
    - numpy floats -> Python float
    - numpy booleans -> Python bool
    - numpy arrays -> Python list

    Example:
        >>> import numpy as np
        >>> import json
        >>> from sleeper_detection.utils.json_encoder import NumpyJSONEncoder
        >>>
        >>> data = {
        ...     'bool_val': np.bool_(True),
        ...     'int_val': np.int64(42),
        ...     'float_val': np.float32(3.14),
        ...     'array': np.array([1, 2, 3])
        ... }
        >>> json.dumps(data, cls=NumpyJSONEncoder)
    """

    def default(self, obj: Any) -> Any:
        """Convert numpy types to Python native types.

        Args:
            obj: Object to be serialized

        Returns:
            Python native type equivalent of numpy type

        Raises:
            TypeError: If the object is not JSON serializable
        """
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        # Let the base class raise the TypeError
        return super().default(obj)
