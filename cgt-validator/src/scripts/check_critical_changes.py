#!/usr/bin/env python3
"""Check for critical template changes and create notification file."""

import json
import logging
import sys
from pathlib import Path

from config.states_config import list_supported_states
from scrapers.template_monitor import TemplateMonitor

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main entry point for checking critical changes."""
    critical_changes = []
    for state in list_supported_states():
        try:
            monitor = TemplateMonitor(state, storage_dir=Path(f"./monitoring/{state}"))
            summary = monitor.run_monitoring()

            if summary.get("critical_changes"):
                critical_changes.extend([{"state": state, **change} for change in summary["critical_changes"]])
        except FileNotFoundError as e:
            logger.warning("Configuration not found for %s: %s", state, e)
        except ConnectionError as e:
            logger.error("Network error monitoring %s: %s", state, e)
        except (AttributeError, KeyError, ValueError) as e:
            logger.error("Unexpected error monitoring %s: %s", state, e)

    if critical_changes:
        print("CRITICAL TEMPLATE CHANGES DETECTED:")
        for change in critical_changes:
            print(f"  - {change['state']}: {change['url']}")
            print(f"    {change['description']}")

        # Save to file for notification
        with open("critical_changes.json", "w", encoding="utf-8") as f:
            json.dump(critical_changes, f, indent=2)

        sys.exit(1)  # Fail the job to trigger notifications

    return 0


if __name__ == "__main__":
    sys.exit(main())
