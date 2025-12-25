"""Core utilities and base classes for MCP servers"""

from .base_server import BaseMCPServer
from .http_proxy import HTTPProxy
from .utils import setup_logging, validate_environment

# Base exports
__all__ = [
    "BaseMCPServer",
    "HTTPProxy",
    "setup_logging",
    "validate_environment",
]

# MCPClient is optional - only import if requests is available
# This allows servers to run without the client dependency
try:
    from .client import MCPClient  # noqa: F401

    __all__.append("MCPClient")
except ImportError:
    # Client not available (likely running in server container without requests)
    pass

# Emotions module - canonical emotion taxonomy for unified expression
# Import lazily to avoid circular import issues in installed packages
try:
    from . import emotions  # noqa: F401

    __all__.append("emotions")
except ImportError:
    pass

# Personality module - memory utilities for expressive AI agents
try:
    from . import personality  # noqa: F401

    __all__.append("personality")
except ImportError:
    pass

# Expression module - multi-modal expression orchestration
try:
    from . import expression  # noqa: F401

    __all__.append("expression")
except ImportError:
    pass
