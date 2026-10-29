"""Async utilities for sleeper detection package.

This module provides utility functions for working with asyncio in the sleeper detection package.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None


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
    global _loop  # pylint: disable=global-statement
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass
    # asyncio.get_event_loop() no longer creates a loop implicitly when none is
    # running (deprecated since Python 3.12, an error from 3.14), so keep and
    # reuse one loop created here instead.
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop
