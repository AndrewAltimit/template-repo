"""Async utilities for sleeper detection package.

This module provides utility functions for working with asyncio in the sleeper detection package.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create an asyncio event loop.

    This utility function handles the common pattern of getting the current event loop
    or creating a new one if none exists. This is useful when running async code from
    synchronous contexts.

    Returns:
        asyncio.AbstractEventLoop: The event loop to use

    Example:
        >>> loop = get_or_create_event_loop()
        >>> result = loop.run_until_complete(my_async_function())
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop
