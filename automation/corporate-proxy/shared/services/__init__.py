"""
Shared services for corporate proxy integrations.

These services provide common functionality for translating between
external AI tool formats and internal corporate API formats.

Supports both OpenAI and Anthropic tool API specifications.
"""

# Import only what exists
try:
    from .mock_api import app as mock_app  # noqa: F401

    __all__ = ["mock_app"]
except ImportError:
    __all__ = []

try:
    from .translation_wrapper import app as translation_app  # noqa: F401

    __all__.append("translation_app")
except ImportError:
    pass

try:
    from .api_spec_converter import APISpecConverter, get_converter  # noqa: F401

    __all__.extend(["APISpecConverter", "get_converter"])
except ImportError:
    pass
