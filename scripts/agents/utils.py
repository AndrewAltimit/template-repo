#!/usr/bin/env python3
"""
Shared utilities for AI agents.
"""

import logging
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


def run_gh_command(args: List[str]) -> Optional[str]:
    """Run GitHub CLI command and return output."""
    try:
        cmd = ["gh"] + args
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"GitHub CLI error: {e.stderr}")
        return None
