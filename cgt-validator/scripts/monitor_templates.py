#!/usr/bin/env python3
"""CLI tool for monitoring CGT template changes."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.states_config import list_supported_states  # noqa: E402
from scrapers.template_monitor import TemplateMonitor  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def monitor_state(args):
    """Monitor templates for a specific state."""
    logger.info(f"Starting template monitoring for {args.state}")

    # Create monitor
    storage_dir = Path(args.storage_dir) / args.state if args.storage_dir else None
    monitor = TemplateMonitor(args.state, storage_dir=storage_dir)

    # Configure monitoring options
    if args.no_direct:
        monitor.monitoring_config["monitor_direct_urls"] = False
    if args.no_scraped:
        monitor.monitoring_config["monitor_scraped_templates"] = False
    if args.no_content:
        monitor.monitoring_config["check_content_changes"] = False
    if args.critical_fields:
        monitor.monitoring_config["critical_fields"] = args.critical_fields

    # Save updated config
    monitor._save_monitoring_config()

    # Run monitoring
    summary = monitor.run_monitoring()

    # Print summary
    print(f"\n{'='*60}")
    print(f"MONITORING SUMMARY - {args.state.upper()}")
    print(f"{'='*60}")
    print(f"URLs monitored: {summary['total_urls_monitored']}")
    print(f"Changes detected: {summary['changes_detected']}")

    if summary["changes_by_type"]:
        print("\nChanges by type:")
        for change_type, count in summary["changes_by_type"].items():
            print(f"  {change_type}: {count}")

    if summary["changes_by_severity"]:
        print("\nChanges by severity:")
        for severity, count in summary["changes_by_severity"].items():
            icon = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "🟢"
            print(f"  {icon} {severity}: {count}")

    if summary["critical_changes"]:
        print("\n⚠️  CRITICAL CHANGES:")
        for change in summary["critical_changes"]:
            print(f"  - {change['url']}")
            print(f"    {change['description']}")

    # Generate report if requested
    if args.report:
        report_format = args.report_format.lower()
        report = monitor.generate_change_report(report_format)

        # Determine output file
        if args.output:
            output_file = Path(args.output)
        else:
            ext = "html" if report_format == "html" else "md"
            output_file = Path(f"{args.state}_monitoring_report.{ext}")

        # Save report
        output_file.write_text(report)
        print(f"\nReport saved to: {output_file}")

    # Save summary if requested
    if args.json:
        json_file = Path(args.json)
        with open(json_file, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"JSON summary saved to: {json_file}")

    # Return exit code based on critical changes
    if summary.get("critical_changes"):
        return 1  # Exit with error if critical changes detected
    return 0


def show_status(args):
    """Show monitoring status for a state."""
    storage_dir = Path(args.storage_dir) / args.state if args.storage_dir else None
    monitor = TemplateMonitor(args.state, storage_dir=storage_dir)

    print(f"\n{'='*60}")
    print(f"MONITORING STATUS - {args.state.upper()}")
    print(f"{'='*60}")

    # Show configuration
    print("\nConfiguration:")
    for key, value in monitor.monitoring_config.items():
        if isinstance(value, list):
            print(f"  {key}: {len(value)} items")
            if key == "critical_fields" and value:
                print(f"    Fields: {', '.join(value[:5])}")
                if len(value) > 5:
                    print(f"    ... and {len(value)-5} more")
        else:
            print(f"  {key}: {value}")

    # Show snapshot status
    print("\nSnapshots:")
    print(f"  Total URLs tracked: {len(monitor.snapshots)}")
    total_snapshots = sum(len(s) for s in monitor.snapshots.values())
    print(f"  Total snapshots: {total_snapshots}")

    # Show recent changes
    if monitor.change_history:
        print("\nChange History:")
        print(f"  Total changes: {len(monitor.change_history)}")

        # Show last 5 changes
        recent = monitor.change_history[-5:]
        if recent:
            print("\n  Recent changes:")
            for change in reversed(recent):
                icon = "🔴" if change.severity == "critical" else "🟡" if change.severity == "warning" else "🟢"
                detected = datetime.fromisoformat(change.detected_at).strftime("%Y-%m-%d %H:%M")
                print(f"    {icon} [{detected}] {change.change_type}: {Path(change.url).name}")

    # Show storage information
    if monitor.storage_dir.exists():
        # Calculate storage size
        total_size = sum(f.stat().st_size for f in monitor.storage_dir.rglob("*") if f.is_file())
        print("\nStorage:")
        print(f"  Directory: {monitor.storage_dir}")
        print(f"  Size: {total_size / 1024 / 1024:.2f} MB")


def clear_history(args):
    """Clear monitoring history for a state."""
    storage_dir = Path(args.storage_dir) / args.state if args.storage_dir else None
    monitor = TemplateMonitor(args.state, storage_dir=storage_dir)

    if not args.force:
        response = input(f"Are you sure you want to clear monitoring history for {args.state}? (y/N): ")
        if response.lower() != "y":
            print("Cancelled")
            return

    # Clear history
    if args.type in ["all", "changes"]:
        monitor.change_history = []
        monitor._save_change_history()
        print("✓ Change history cleared")

    if args.type in ["all", "snapshots"]:
        monitor.snapshots = {}
        monitor._save_snapshots()
        print("✓ Snapshots cleared")

    print(f"History cleared for {args.state}")


def monitor_all(args):
    """Monitor all supported states."""
    states = list_supported_states()
    results = {}

    print(f"Monitoring {len(states)} states...")

    for state in states:
        print(f"\n{'='*40}")
        print(f"Monitoring {state}...")
        print(f"{'='*40}")

        try:
            storage_dir = Path(args.storage_dir) / state if args.storage_dir else None
            monitor = TemplateMonitor(state, storage_dir=storage_dir)
            summary = monitor.run_monitoring()

            results[state] = {
                "success": True,
                "changes": summary["changes_detected"],
                "critical": len(summary.get("critical_changes", [])),
            }

            print(f"✓ {state}: {summary['changes_detected']} changes detected")

        except Exception as e:
            logger.error(f"Error monitoring {state}: {e}")
            results[state] = {
                "success": False,
                "error": str(e),
            }
            print(f"✗ {state}: Failed")

    # Print summary
    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print(f"{'='*60}")

    successful = sum(1 for r in results.values() if r.get("success"))
    total_changes = sum(r.get("changes", 0) for r in results.values())
    total_critical = sum(r.get("critical", 0) for r in results.values())

    print(f"States monitored: {successful}/{len(states)}")
    print(f"Total changes: {total_changes}")
    print(f"Critical changes: {total_critical}")

    if args.json:
        json_file = Path(args.json)
        with open(json_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {json_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor CGT templates for changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor Oregon templates
  %(prog)s monitor oregon

  # Monitor with report generation
  %(prog)s monitor oregon --report --report-format markdown

  # Monitor all states
  %(prog)s monitor-all

  # Show monitoring status
  %(prog)s status oregon

  # Clear monitoring history
  %(prog)s clear oregon --type all
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor templates for a state")
    monitor_parser.add_argument("state", choices=list_supported_states(), help="State to monitor")
    monitor_parser.add_argument("--storage-dir", help="Storage directory for monitoring data")
    monitor_parser.add_argument("--no-direct", action="store_true", help="Skip monitoring direct URLs")
    monitor_parser.add_argument("--no-scraped", action="store_true", help="Skip monitoring scraped templates")
    monitor_parser.add_argument("--no-content", action="store_true", help="Skip content change detection")
    monitor_parser.add_argument("--critical-fields", nargs="+", help="Critical fields to track")
    monitor_parser.add_argument("--report", action="store_true", help="Generate change report")
    monitor_parser.add_argument("--report-format", choices=["markdown", "html"], default="markdown", help="Report format")
    monitor_parser.add_argument("--output", help="Output file for report")
    monitor_parser.add_argument("--json", help="Save summary as JSON")

    # Monitor all command
    monitor_all_parser = subparsers.add_parser("monitor-all", help="Monitor all supported states")
    monitor_all_parser.add_argument("--storage-dir", help="Storage directory for monitoring data")
    monitor_all_parser.add_argument("--json", help="Save results as JSON")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show monitoring status")
    status_parser.add_argument("state", choices=list_supported_states(), help="State to check")
    status_parser.add_argument("--storage-dir", help="Storage directory for monitoring data")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear monitoring history")
    clear_parser.add_argument("state", choices=list_supported_states(), help="State to clear")
    clear_parser.add_argument("--type", choices=["all", "changes", "snapshots"], default="all", help="What to clear")
    clear_parser.add_argument("--storage-dir", help="Storage directory for monitoring data")
    clear_parser.add_argument("--force", action="store_true", help="Skip confirmation")

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    try:
        if args.command == "monitor":
            return monitor_state(args)
        elif args.command == "monitor-all":
            return monitor_all(args)
        elif args.command == "status":
            show_status(args)
            return 0
        elif args.command == "clear":
            clear_history(args)
            return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
