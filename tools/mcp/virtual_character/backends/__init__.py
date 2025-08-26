"""
Virtual Character backend adapters.
"""

from .base import BackendAdapter, BackendCapabilities
from .mock import MockBackend

# Import VRChat backend if dependencies are available
try:
    from .vrchat_remote import VRChatRemoteBackend  # noqa: F401

    HAS_VRCHAT = True
    __all__ = ["BackendAdapter", "BackendCapabilities", "MockBackend", "VRChatRemoteBackend"]
except ImportError:
    HAS_VRCHAT = False
    __all__ = ["BackendAdapter", "BackendCapabilities", "MockBackend"]
