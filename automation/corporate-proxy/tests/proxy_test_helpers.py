"""
Shared test utilities for corporate proxy tests.

The tool-call formatting tests exercise the production implementation and the
production mapping file (shared/configs/opencode_param_mappings.json) directly,
so a change to either is covered without keeping a copy in sync here.
"""

from pathlib import Path
import sys

_SERVICES = Path(__file__).resolve().parent.parent / "shared" / "services"
if str(_SERVICES) not in sys.path:
    # translation_wrapper imports its sibling modules by bare name
    sys.path.insert(0, str(_SERVICES))

from translation_wrapper import (  # noqa: E402
    OPENCODE_PARAM_MAPPINGS,
    OPENCODE_TOOL_RENAMES,
    format_tool_calls_for_openai,
)

# Re-export for convenient test imports
__all__ = ["format_tool_calls_for_openai", "OPENCODE_PARAM_MAPPINGS", "OPENCODE_TOOL_RENAMES"]
