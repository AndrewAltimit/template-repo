#!/usr/bin/env python3
"""Check for critical template changes and create notification file."""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scrapers.template_monitor import TemplateMonitor  # noqa: E402

critical_changes = []
for state in ["oregon", "massachusetts", "rhode_island", "washington"]:
    try:
        monitor = TemplateMonitor(state, storage_dir=Path(f"./monitoring/{state}"))
        summary = monitor.run_monitoring()

        if summary.get("critical_changes"):
            critical_changes.extend([{"state": state, **change} for change in summary["critical_changes"]])
    except Exception as e:
        print(f"Error monitoring {state}: {e}")

if critical_changes:
    print("CRITICAL TEMPLATE CHANGES DETECTED:")
    for change in critical_changes:
        print(f"  - {change['state']}: {change['url']}")
        print(f"    {change['description']}")

    # Save to file for notification
    with open("critical_changes.json", "w") as f:
        json.dump(critical_changes, f, indent=2)

    sys.exit(1)  # Fail the job to trigger notifications
