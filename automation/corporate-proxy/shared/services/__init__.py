"""
Shared services for corporate proxy integrations.

These services provide common functionality for translating between
external AI tool formats and internal corporate API formats.
"""

# Import only what exists
try:
    from .mock_api import app as mock_app

    __all__ = ["mock_app"]
except ImportError:
    __all__ = []

try:
    from .translation_wrapper import app as translation_app

    __all__.append("translation_app")
except ImportError:
    pass
