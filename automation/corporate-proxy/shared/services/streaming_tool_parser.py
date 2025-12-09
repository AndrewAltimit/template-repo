#!/usr/bin/env python3
"""
Streaming Tool Parser for AI Agent Integration

Handles stateful parsing of streaming AI responses with buffering for incomplete tool calls.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from .text_tool_parser import TextToolParser

logger = logging.getLogger(__name__)


class StreamingToolParser:
    """
    Stateful parser for handling streaming AI responses.

    Buffers incomplete tool calls and parses them when complete.
    """

    def __init__(
        self,
        allowed_tools: Optional[Set[str]] = None,
        max_json_size: int = 1 * 1024 * 1024,
        max_buffer_size: int = 10 * 1024 * 1024,  # 10MB buffer limit
    ):
        """
        Initialize the streaming parser.

        Args:
            allowed_tools: Set of permitted tool names.
            max_json_size: Maximum size for a single JSON payload.
            max_buffer_size: Maximum size for the internal buffer.
        """
        self.parser = TextToolParser(allowed_tools=allowed_tools, max_json_size=max_json_size)
        self.buffer = ""
        self.max_buffer_size = max_buffer_size
        self.completed_tool_calls = []

    def process_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """
        Process a streaming chunk and extract any complete tool calls.

        Args:
            chunk: New text chunk from the stream.

        Returns:
            List of newly completed tool calls.
        """
        self.buffer += chunk

        # Security: Prevent buffer overflow
        if len(self.buffer) > self.max_buffer_size:
            logger.error("Buffer overflow, clearing buffer (size: %d)", len(self.buffer))
            self.buffer = ""
            return []

        new_tool_calls = []

        # Look for complete JSON blocks
        json_pattern = r"```(?:tool_call|tool_code|json)\s*\n.*?\n\s*```"
        json_matches = list(re.finditer(json_pattern, self.buffer, re.DOTALL))

        # Look for complete XML blocks
        xml_pattern = r"<tool>.*?</tool>"
        xml_matches = list(re.finditer(xml_pattern, self.buffer, re.DOTALL))

        # Process and remove complete blocks from buffer
        all_matches = sorted(json_matches + xml_matches, key=lambda m: m.start())

        offset = 0
        for match in all_matches:
            # Parse the complete block
            block_text = match.group()
            parsed = self.parser.parse_tool_calls(block_text)

            for tool_call in parsed:
                # Avoid duplicates
                if tool_call not in self.completed_tool_calls:
                    new_tool_calls.append(tool_call)
                    self.completed_tool_calls.append(tool_call)

            # Mark this section for removal from buffer
            offset = match.end()

        # Remove processed content from buffer
        if offset > 0:
            self.buffer = self.buffer[offset:]

        return new_tool_calls

    def flush(self) -> List[Dict[str, Any]]:
        """
        Process any remaining buffer content at stream end.

        Returns:
            Any tool calls found in the remaining buffer.
        """
        if not self.buffer:
            return []

        # Try to parse whatever is left
        remaining_calls = self.parser.parse_tool_calls(self.buffer)
        self.buffer = ""

        # Filter out duplicates
        new_calls = []
        for call in remaining_calls:
            if call not in self.completed_tool_calls:
                new_calls.append(call)
                self.completed_tool_calls.append(call)

        return new_calls

    def reset(self):
        """Reset the parser state for a new stream."""
        self.buffer = ""
        self.completed_tool_calls = []
        self.parser.reset_stats()
