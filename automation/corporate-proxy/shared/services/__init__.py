"""
Shared services for corporate proxy integrations.

These services provide common functionality for translating between
external AI tool formats and internal corporate API formats.
"""

from .mock_api import app as mock_app
from .translation_wrapper import app as translation_app

__all__ = ["translation_app", "mock_app"]
