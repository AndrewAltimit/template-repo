"""Core utilities and base classes for MCP servers"""

from .base_server import BaseMCPServer
from .http_proxy import HTTPProxy
from .utils import setup_logging, validate_environment

# MCPClient is optional - only import if requests is available
# This allows servers to run without the client dependency
try:
    from .client import MCPClient  # noqa: F401

    __all__ = [
        "BaseMCPServer",
        "MCPClient",
        "HTTPProxy",
        "setup_logging",
        "validate_environment",
    ]
except ImportError:
    # Client not available (likely running in server container without requests)
    __all__ = ["BaseMCPServer", "HTTPProxy", "setup_logging", "validate_environment"]
