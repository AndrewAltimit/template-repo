"""String utility helpers for GitHub AI Agents."""

from __future__ import annotations


def reverse_string(value: str) -> str:
    """Return the reversed version of ``value``.

    Args:
        value: The string to reverse.

    Returns:
        str: The reversed string.
    """
    return value[::-1]
