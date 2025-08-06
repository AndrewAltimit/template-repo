#!/usr/bin/env python3
"""CLI tool for monitoring CGT template changes."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import click

from config.states_config import list_supported_states
from scrapers.template_monitor import TemplateMonitor

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Monitor CGT templates for changes."""


@cli.command()
@click.argument("state", type=click.Choice(list_supported_states()))
@click.option("--storage-dir", type=click.Path(), help="Storage directory for monitoring data")
@click.option("--no-direct", is_flag=True, help="Skip monitoring direct URLs")
@click.option("--no-scraped", is_flag=True, help="Skip monitoring scraped templates")
@click.option("--no-content", is_flag=True, help="Skip content change detection")
@click.option("--critical-fields", multiple=True, help="Critical fields to track")
@click.option("--report", is_flag=True, help="Generate change report")
@click.option("--report-format", type=click.Choice(["markdown", "html"]), default="markdown", help="Report format")
@click.option("--output", type=click.Path(), help="Output file for report")
@click.option("--json", "json_output", type=click.Path(), help="Save summary as JSON")
def monitor(
    state, storage_dir, no_direct, no_scraped, no_content, critical_fields, report, report_format, output, json_output
):
    """Monitor templates for a specific state."""
    logger.info(f"Starting template monitoring for {state}")

    # Create monitor
    storage_path = Path(storage_dir) / state if storage_dir else None
    monitor_obj = TemplateMonitor(state, storage_dir=storage_path)

    # Configure monitoring options
    if no_direct:
        monitor_obj.monitoring_config["monitor_direct_urls"] = False
    if no_scraped:
        monitor_obj.monitoring_config["monitor_scraped_templates"] = False
    if no_content:
        monitor_obj.monitoring_config["check_content_changes"] = False
    if critical_fields:
        monitor_obj.monitoring_config["critical_fields"] = list(critical_fields)

    # Save updated config
    monitor_obj._save_monitoring_config()

    # Run monitoring
    try:
        summary = monitor_obj.run_monitoring()
    except FileNotFoundError as e:
        logger.error(f"Configuration not found: {e}")
        sys.exit(1)
    except ConnectionError as e:
        logger.error(f"Network error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

    # Print summary
    click.echo(f"\n{'='*60}")
    click.echo(f"MONITORING SUMMARY - {state.upper()}")
    click.echo(f"{'='*60}")
    click.echo(f"URLs monitored: {summary['total_urls_monitored']}")
    click.echo(f"Changes detected: {summary['changes_detected']}")

    if summary["changes_by_type"]:
        click.echo("\nChanges by type:")
        for change_type, count in summary["changes_by_type"].items():
            click.echo(f"  {change_type}: {count}")

    if summary["changes_by_severity"]:
        click.echo("\nChanges by severity:")
        for severity, count in summary["changes_by_severity"].items():
            icon = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "🟢"
            click.echo(f"  {icon} {severity}: {count}")

    if summary["critical_changes"]:
        click.echo("\n⚠️  CRITICAL CHANGES:")
        for change in summary["critical_changes"]:
            click.echo(f"  - {change['url']}")
            click.echo(f"    {change['description']}")

    # Generate report if requested
    if report:
        report_content = monitor_obj.generate_change_report(report_format)

        # Determine output file
        if output:
            output_file = Path(output)
        else:
            ext = "html" if report_format == "html" else "md"
            output_file = Path(f"{state}_monitoring_report.{ext}")

        # Save report
        output_file.write_text(report_content)
        click.echo(f"\nReport saved to: {output_file}")

    # Save summary if requested
    if json_output:
        json_file = Path(json_output)
        with open(json_file, "w") as f:
            json.dump(summary, f, indent=2)
        click.echo(f"JSON summary saved to: {json_file}")

    # Exit with error if critical changes detected
    if summary.get("critical_changes"):
        sys.exit(1)


@cli.command()
@click.argument("state", type=click.Choice(list_supported_states()))
@click.option("--storage-dir", type=click.Path(), help="Storage directory for monitoring data")
def status(state, storage_dir):
    """Show monitoring status for a state."""
    storage_path = Path(storage_dir) / state if storage_dir else None
    monitor_obj = TemplateMonitor(state, storage_dir=storage_path)

    click.echo(f"\n{'='*60}")
    click.echo(f"MONITORING STATUS - {state.upper()}")
    click.echo(f"{'='*60}")

    # Show configuration
    click.echo("\nConfiguration:")
    for key, value in monitor_obj.monitoring_config.items():
        if isinstance(value, list):
            click.echo(f"  {key}: {len(value)} items")
            if key == "critical_fields" and value:
                click.echo(f"    Fields: {', '.join(value[:5])}")
                if len(value) > 5:
                    click.echo(f"    ... and {len(value)-5} more")
        else:
            click.echo(f"  {key}: {value}")

    # Show snapshot status
    click.echo("\nSnapshots:")
    click.echo(f"  Total URLs tracked: {len(monitor_obj.snapshots)}")
    total_snapshots = sum(len(s) for s in monitor_obj.snapshots.values())
    click.echo(f"  Total snapshots: {total_snapshots}")

    # Show recent changes
    if monitor_obj.change_history:
        click.echo("\nChange History:")
        click.echo(f"  Total changes: {len(monitor_obj.change_history)}")

        # Show last 5 changes
        recent = monitor_obj.change_history[-5:]
        if recent:
            click.echo("\n  Recent changes:")
            for change in reversed(recent):
                icon = "🔴" if change.severity == "critical" else "🟡" if change.severity == "warning" else "🟢"
                detected = datetime.fromisoformat(change.detected_at).strftime("%Y-%m-%d %H:%M")
                click.echo(f"    {icon} [{detected}] {change.change_type}: {Path(change.url).name}")

    # Show storage information
    if monitor_obj.storage_dir.exists():
        # Calculate storage size
        total_size = sum(f.stat().st_size for f in monitor_obj.storage_dir.rglob("*") if f.is_file())
        click.echo("\nStorage:")
        click.echo(f"  Directory: {monitor_obj.storage_dir}")
        click.echo(f"  Size: {total_size / 1024 / 1024:.2f} MB")


@cli.command()
@click.argument("state", type=click.Choice(list_supported_states()))
@click.option(
    "--type", "clear_type", type=click.Choice(["all", "changes", "snapshots"]), default="all", help="What to clear"
)
@click.option("--storage-dir", type=click.Path(), help="Storage directory for monitoring data")
@click.option("--force", is_flag=True, help="Skip confirmation")
def clear(state, clear_type, storage_dir, force):
    """Clear monitoring history for a state."""
    storage_path = Path(storage_dir) / state if storage_dir else None
    monitor_obj = TemplateMonitor(state, storage_dir=storage_path)

    if not force:
        # In non-interactive environments (CI/containers), skip confirmation
        # Users must explicitly use --force flag
        if not sys.stdin.isatty():
            click.echo("Error: Non-interactive environment detected. Use --force flag to skip confirmation.")
            sys.exit(1)

        if not click.confirm(f"Are you sure you want to clear monitoring history for {state}?"):
            click.echo("Cancelled")
            return

    # Clear history
    if clear_type in ["all", "changes"]:
        monitor_obj.change_history = []
        monitor_obj._save_change_history()
        click.echo("✓ Change history cleared")

    if clear_type in ["all", "snapshots"]:
        monitor_obj.snapshots = {}
        monitor_obj._save_snapshots()
        click.echo("✓ Snapshots cleared")

    click.echo(f"History cleared for {state}")


@cli.command("monitor-all")
@click.option("--storage-dir", type=click.Path(), help="Storage directory for monitoring data")
@click.option("--json", "json_output", type=click.Path(), help="Save results as JSON")
def monitor_all(storage_dir, json_output):
    """Monitor all supported states."""
    states = list_supported_states()
    results = {}

    click.echo(f"Monitoring {len(states)} states...")

    for state in states:
        click.echo(f"\n{'='*40}")
        click.echo(f"Monitoring {state}...")
        click.echo(f"{'='*40}")

        try:
            storage_path = Path(storage_dir) / state if storage_dir else None
            monitor_obj = TemplateMonitor(state, storage_dir=storage_path)
            summary = monitor_obj.run_monitoring()

            results[state] = {
                "success": True,
                "changes": summary["changes_detected"],
                "critical": len(summary.get("critical_changes", [])),
            }

            click.echo(f"✓ {state}: {summary['changes_detected']} changes detected")

        except FileNotFoundError as e:
            logger.warning(f"Configuration not found for {state}: {e}")
            results[state] = {
                "success": False,
                "error": f"Configuration not found: {e}",
            }
            click.echo(f"✗ {state}: Configuration not found")
        except ConnectionError as e:
            logger.error(f"Network error monitoring {state}: {e}")
            results[state] = {
                "success": False,
                "error": f"Network error: {e}",
            }
            click.echo(f"✗ {state}: Network error")
        except Exception as e:
            logger.error(f"Unexpected error monitoring {state}: {e}")
            results[state] = {
                "success": False,
                "error": str(e),
            }
            click.echo(f"✗ {state}: Failed")

    # Print summary
    click.echo(f"\n{'='*60}")
    click.echo("OVERALL SUMMARY")
    click.echo(f"{'='*60}")

    successful = sum(1 for r in results.values() if r.get("success"))
    total_changes = sum(r.get("changes", 0) for r in results.values())
    total_critical = sum(r.get("critical", 0) for r in results.values())

    click.echo(f"States monitored: {successful}/{len(states)}")
    click.echo(f"Total changes: {total_changes}")
    click.echo(f"Critical changes: {total_critical}")

    if json_output:
        json_file = Path(json_output)
        with open(json_file, "w") as f:
            json.dump(results, f, indent=2)
        click.echo(f"\nResults saved to: {json_file}")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    sys.exit(main())
