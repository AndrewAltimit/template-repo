"""Tests for string utility helpers."""

from github_ai_agents.utils import reverse_string


def test_reverse_string_basic():
    """Reverse a regular string."""
    assert reverse_string("hello") == "olleh"


def test_reverse_string_preserves_whitespace():
    """Ensure whitespace remains in the reversed order."""
    assert reverse_string("abc def") == "fed cba"


def test_reverse_string_empty():
    """Reverse an empty string."""
    assert reverse_string("") == ""
