"""Template monitoring system with change detection and notification."""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from config.states_config import get_state_config

from .document_downloader import DocumentDownloader
from .web_scraper import DocumentInfo, WebScraper

logger = logging.getLogger(__name__)


class TemplateSnapshot:
    """Snapshot of a template at a point in time."""

    def __init__(
        self,
        url: str,
        file_hash: str,
        file_size: int,
        content_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        snapshot_date: Optional[str] = None,
    ):
        self.url = url
        self.file_hash = file_hash
        self.file_size = file_size
        self.content_hash = content_hash  # Hash of extracted text content
        self.metadata = metadata or {}
        self.snapshot_date = snapshot_date or datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "snapshot_date": self.snapshot_date,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TemplateSnapshot":
        """Create from dictionary."""
        return cls(
            url=data["url"],
            file_hash=data["file_hash"],
            file_size=data["file_size"],
            content_hash=data.get("content_hash"),
            metadata=data.get("metadata", {}),
            snapshot_date=data["snapshot_date"],
        )


class ChangeEvent:
    """Represents a change detected in a template."""

    def __init__(
        self,
        url: str,
        change_type: str,
        old_snapshot: Optional[TemplateSnapshot],
        new_snapshot: Optional[TemplateSnapshot],
        description: str,
        severity: str = "info",
    ):
        self.url = url
        self.change_type = change_type  # new, modified, removed, structure_change
        self.old_snapshot = old_snapshot
        self.new_snapshot = new_snapshot
        self.description = description
        self.severity = severity  # info, warning, critical
        self.detected_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "change_type": self.change_type,
            "old_snapshot": self.old_snapshot.to_dict() if self.old_snapshot else None,
            "new_snapshot": self.new_snapshot.to_dict() if self.new_snapshot else None,
            "description": self.description,
            "severity": self.severity,
            "detected_at": self.detected_at,
        }


class TemplateMonitor:
    """Monitor templates for changes and generate notifications."""

    def __init__(self, state_name: str, storage_dir: Optional[Path] = None):
        self.state = state_name
        self.config = get_state_config(state_name)
        self.storage_dir = storage_dir or Path(f"./monitoring/{state_name}")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Storage paths
        self.snapshots_file = self.storage_dir / "template_snapshots.json"
        self.changes_file = self.storage_dir / "change_history.json"
        self.monitoring_config_file = self.storage_dir / "monitoring_config.json"

        # Load existing data
        self.snapshots = self._load_snapshots()
        self.change_history = self._load_change_history()
        self.monitoring_config = self._load_monitoring_config()

        # Initialize empty files if they don't exist
        if not self.snapshots_file.exists():
            self._save_snapshots()
        if not self.changes_file.exists():
            self._save_change_history()
        if not self.monitoring_config_file.exists():
            self._save_monitoring_config()

        # Initialize components
        self.scraper = WebScraper(state_name, cache_dir=self.storage_dir / "cache")
        self.downloader = DocumentDownloader(state_name, storage_dir=self.storage_dir / "downloads")

        # Session for downloading
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 CGT-Validator/1.0"})

    def _load_snapshots(self) -> Dict[str, List[TemplateSnapshot]]:
        """Load template snapshots from file."""
        if self.snapshots_file.exists():
            with open(self.snapshots_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {url: [TemplateSnapshot.from_dict(s) for s in snapshots] for url, snapshots in data.items()}
        return {}

    def _save_snapshots(self):
        """Save template snapshots to file."""
        data = {url: [s.to_dict() for s in snapshots] for url, snapshots in self.snapshots.items()}
        with open(self.snapshots_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_change_history(self) -> List[ChangeEvent]:
        """Load change history from file."""
        if self.changes_file.exists():
            with open(self.changes_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [
                    ChangeEvent(
                        url=c["url"],
                        change_type=c["change_type"],
                        old_snapshot=TemplateSnapshot.from_dict(c["old_snapshot"]) if c["old_snapshot"] else None,
                        new_snapshot=TemplateSnapshot.from_dict(c["new_snapshot"]) if c["new_snapshot"] else None,
                        description=c["description"],
                        severity=c.get("severity", "info"),
                    )
                    for c in data
                ]
        return []

    def _save_change_history(self):
        """Save change history to file."""
        data = [c.to_dict() for c in self.change_history]
        with open(self.changes_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_monitoring_config(self) -> Dict:
        """Load monitoring configuration."""
        if self.monitoring_config_file.exists():
            with open(self.monitoring_config_file, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore

        # Default configuration
        return {
            "monitor_direct_urls": True,
            "monitor_scraped_templates": True,
            "check_content_changes": True,
            "extract_text_from_pdfs": True,
            "track_field_changes": True,
            "critical_fields": ["PROV_ID", "MEMBER_MONTHS", "PAID_AMT"],
            "notification_threshold": "warning",  # info, warning, critical
            "max_snapshots_per_url": 10,
        }

    def _save_monitoring_config(self):
        """Save monitoring configuration."""
        with open(self.monitoring_config_file, "w", encoding="utf-8") as f:
            json.dump(self.monitoring_config, f, indent=2)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as file_handle:
            for byte_block in iter(lambda: file_handle.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _extract_text_content(self, file_path: Path) -> Optional[str]:
        """Extract text content from a file for deeper comparison."""
        if not self.monitoring_config.get("extract_text_from_pdfs"):
            return None

        file_type = file_path.suffix.lower()

        if file_type == ".pdf":
            try:
                import PyPDF2

                with open(file_path, "rb") as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text()
                return text
            except (ImportError, AttributeError, ValueError, IOError) as e:
                logger.warning("Could not extract text from PDF %s: %s", file_path, e)
                return None

        elif file_type in [".txt", ".csv"]:
            try:
                with open(file_path, "r", encoding="utf-8") as text_file:
                    return text_file.read()
            except (IOError, UnicodeDecodeError) as e:
                logger.warning("Could not read text file %s: %s", file_path, e)
                return None

        elif file_type in [".xlsx", ".xls", ".xlsm"]:
            try:
                import openpyxl

                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                text = ""
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        text += " ".join(str(cell) for cell in row if cell) + "\n"
                return text
            except (ImportError, AttributeError, ValueError, IOError) as e:
                logger.warning("Could not extract text from Excel %s: %s", file_path, e)
                return None

        return None

    def _detect_field_changes(self, old_text: str, new_text: str) -> List[str]:
        """Detect changes in critical fields between two text versions."""
        if not self.monitoring_config.get("track_field_changes"):
            return []

        critical_fields = self.monitoring_config.get("critical_fields", [])
        changed_fields = []

        for field in critical_fields:
            # Look for field patterns in both texts
            old_pattern = re.findall(rf"{field}[:\s]*([^\n]+)", old_text, re.IGNORECASE)
            new_pattern = re.findall(rf"{field}[:\s]*([^\n]+)", new_text, re.IGNORECASE)

            if old_pattern != new_pattern:
                changed_fields.append(field)

        return changed_fields

    def _download_and_snapshot(self, url: str, doc_info: Optional[DocumentInfo] = None) -> Optional[TemplateSnapshot]:
        """Download a document and create a snapshot."""
        try:
            # Security: Check file size before downloading (max 100MB)
            head_response = self.session.head(url, timeout=10, allow_redirects=True)
            content_length = head_response.headers.get("content-length")
            if content_length and int(content_length) > 100 * 1024 * 1024:
                logger.warning("File too large to download: %s (%.1f MB)", url, int(content_length) / 1024 / 1024)
                return None

            # Download to temporary location
            temp_file = self.storage_dir / "temp" / f"download_{hashlib.md5(url.encode()).hexdigest()}"
            temp_file.parent.mkdir(parents=True, exist_ok=True)

            response = self.session.get(url, timeout=60)
            response.raise_for_status()

            with open(temp_file, "wb") as temp_f:
                temp_f.write(response.content)

            # Calculate hashes
            file_hash = self._calculate_file_hash(temp_file)
            file_size = temp_file.stat().st_size

            # Extract text content for deeper comparison
            text_content = self._extract_text_content(temp_file)
            content_hash = None
            if text_content:
                content_hash = hashlib.sha256(text_content.encode()).hexdigest()

            # Create metadata
            metadata = {
                "filename": Path(urlparse(url).path).name,
                "download_date": datetime.now().isoformat(),
                "content_type": response.headers.get("content-type", "unknown"),
                "last_modified": response.headers.get("last-modified", "unknown"),
            }

            if doc_info:
                metadata["title"] = doc_info.title
                metadata["version"] = doc_info.version or ""
                metadata["file_type"] = doc_info.file_type

            # Move to permanent location
            permanent_file = self.storage_dir / "snapshots" / f"{file_hash[:8]}_{metadata['filename']}"
            permanent_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.rename(permanent_file)

            # Create snapshot
            snapshot = TemplateSnapshot(
                url=url,
                file_hash=file_hash,
                file_size=file_size,
                content_hash=content_hash,
                metadata=metadata,
            )

            return snapshot

        except (requests.RequestException, IOError, OSError) as e:
            logger.error("Error downloading %s: %s", url, e)
            return None

    def _compare_snapshots(self, old: TemplateSnapshot, new: TemplateSnapshot) -> Tuple[bool, str, str]:
        """Compare two snapshots and determine change type and severity."""
        if old.file_hash == new.file_hash:
            return False, "", "info"

        # File changed
        changes = []
        severity = "info"  # Start with info, escalate based on changes

        # Priority 1: Check content hash (most reliable indicator)
        if old.content_hash and new.content_hash:
            if old.content_hash != new.content_hash:
                changes.append("Content structure changed")
                severity = "warning"

            # Try to identify specific field changes
            if self.monitoring_config.get("track_field_changes"):
                old_file = (
                    self.storage_dir / "snapshots" / f"{old.file_hash[:8]}_{old.metadata.get('filename', 'unknown')}"
                )
                new_file = (
                    self.storage_dir / "snapshots" / f"{new.file_hash[:8]}_{new.metadata.get('filename', 'unknown')}"
                )

                if old_file.exists() and new_file.exists():
                    old_text = self._extract_text_content(old_file)
                    new_text = self._extract_text_content(new_file)

                    if old_text and new_text:
                        changed_fields = self._detect_field_changes(old_text, new_text)
                        if changed_fields:
                            changes.append(f"Critical fields changed: {', '.join(changed_fields)}")
                            severity = "critical"  # Critical fields are always critical

        # Priority 2: Size change as secondary indicator (less reliable)
        size_change = new.file_size - old.file_size
        if abs(size_change) > old.file_size * 0.1:  # More than 10% change
            changes.append(f"Significant size change: {size_change:+d} bytes")
            # Only escalate to warning if not already critical
            if severity != "critical":
                severity = "warning"

        # Check version change
        old_version = old.metadata.get("version", "unknown")
        new_version = new.metadata.get("version", "unknown")
        if old_version != new_version:
            changes.append(f"Version changed: {old_version} → {new_version}")

        description = "; ".join(changes) if changes else "File content changed"
        return True, description, severity

    def monitor_direct_urls(self) -> List[ChangeEvent]:
        """Monitor direct URLs for changes."""
        if not self.monitoring_config.get("monitor_direct_urls", True):
            return []

        changes = []
        logger.info("Monitoring direct URLs for %s", self.state)

        for url_config in self.config["direct_urls"]:
            url = url_config["url"]
            logger.info("Checking %s", url)

            # Download and create snapshot
            new_snapshot = self._download_and_snapshot(url)
            if not new_snapshot:
                continue

            # Compare with existing snapshots
            if url in self.snapshots and self.snapshots[url]:
                latest_snapshot = self.snapshots[url][-1]
                changed, description, severity = self._compare_snapshots(latest_snapshot, new_snapshot)

                if changed:
                    change_event = ChangeEvent(
                        url=url,
                        change_type="modified",
                        old_snapshot=latest_snapshot,
                        new_snapshot=new_snapshot,
                        description=description,
                        severity=severity,
                    )
                    changes.append(change_event)

                    # Add to snapshots
                    self.snapshots[url].append(new_snapshot)

                    # Limit snapshots per URL
                    max_snapshots = self.monitoring_config.get("max_snapshots_per_url", 10)
                    if len(self.snapshots[url]) > max_snapshots:
                        self.snapshots[url] = self.snapshots[url][-max_snapshots:]
            else:
                # New URL being tracked
                change_event = ChangeEvent(
                    url=url,
                    change_type="new",
                    old_snapshot=None,
                    new_snapshot=new_snapshot,
                    description=f"New template discovered: {url_config.get('description', 'Unknown')}",
                    severity="info",
                )
                changes.append(change_event)

                # Initialize snapshots for this URL
                self.snapshots[url] = [new_snapshot]

        return changes

    def monitor_scraped_templates(self) -> List[ChangeEvent]:
        """Monitor templates found through web scraping."""
        if not self.monitoring_config.get("monitor_scraped_templates", True):
            return []

        changes = []
        logger.info("Scraping and monitoring templates for %s", self.state)

        # Scrape for templates
        scraped_docs = self.scraper.find_latest_templates()

        # Track which URLs we've seen in this run
        seen_urls = set()

        for doc in scraped_docs:
            url = doc.url
            seen_urls.add(url)

            # Download and create snapshot
            new_snapshot = self._download_and_snapshot(url, doc)
            if not new_snapshot:
                continue

            # Compare with existing snapshots
            if url in self.snapshots and self.snapshots[url]:
                latest_snapshot = self.snapshots[url][-1]
                changed, description, severity = self._compare_snapshots(latest_snapshot, new_snapshot)

                if changed:
                    change_event = ChangeEvent(
                        url=url,
                        change_type="modified",
                        old_snapshot=latest_snapshot,
                        new_snapshot=new_snapshot,
                        description=description,
                        severity=severity,
                    )
                    changes.append(change_event)

                    # Add to snapshots
                    self.snapshots[url].append(new_snapshot)

                    # Limit snapshots per URL
                    max_snapshots = self.monitoring_config.get("max_snapshots_per_url", 10)
                    if len(self.snapshots[url]) > max_snapshots:
                        self.snapshots[url] = self.snapshots[url][-max_snapshots:]
            else:
                # New URL being tracked
                change_event = ChangeEvent(
                    url=url,
                    change_type="new",
                    old_snapshot=None,
                    new_snapshot=new_snapshot,
                    description=f"New template discovered: {doc.title}",
                    severity="info",
                )
                changes.append(change_event)

                # Initialize snapshots for this URL
                self.snapshots[url] = [new_snapshot]

        # Check for removed templates
        for url in self.snapshots.keys():
            if url not in seen_urls and not any(url == uc["url"] for uc in self.config["direct_urls"]):
                # Template no longer found
                removed_snapshot: Optional[TemplateSnapshot] = self.snapshots[url][-1] if self.snapshots[url] else None
                change_event = ChangeEvent(
                    url=url,
                    change_type="removed",
                    old_snapshot=removed_snapshot,
                    new_snapshot=None,
                    description="Template no longer available at this URL",
                    severity="warning",
                )
                changes.append(change_event)

        return changes

    def run_monitoring(self) -> Dict[str, Any]:
        """Run complete monitoring cycle."""
        logger.info("Starting monitoring for %s", self.state)
        start_time = datetime.now()

        all_changes = []

        # Monitor direct URLs
        direct_changes = self.monitor_direct_urls()
        all_changes.extend(direct_changes)

        # Monitor scraped templates
        scraped_changes = self.monitor_scraped_templates()
        all_changes.extend(scraped_changes)

        # Save snapshots and changes
        self._save_snapshots()

        # Add to change history
        self.change_history.extend(all_changes)
        self._save_change_history()

        # Generate summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        monitoring_summary = {
            "state": self.state,
            "monitoring_date": start_time.isoformat(),
            "duration_seconds": duration,
            "total_urls_monitored": len(self.snapshots),
            "changes_detected": len(all_changes),
            "changes_by_type": {},
            "changes_by_severity": {},
            "critical_changes": [],
            "changes": [c.to_dict() for c in all_changes],
        }

        # Categorize changes
        for change_event in all_changes:
            # By type
            changes_by_type: Dict[str, int] = monitoring_summary["changes_by_type"]  # type: ignore
            changes_by_type[change_event.change_type] = changes_by_type.get(change_event.change_type, 0) + 1

            # By severity
            changes_by_severity: Dict[str, int] = monitoring_summary["changes_by_severity"]  # type: ignore
            changes_by_severity[change_event.severity] = changes_by_severity.get(change_event.severity, 0) + 1

            # Track critical changes
            if change_event.severity == "critical":
                monitoring_summary["critical_changes"].append(  # type: ignore
                    {
                        "url": change_event.url,
                        "description": change_event.description,
                    }
                )

        # Save summary
        summary_file = self.storage_dir / f"monitoring_summary_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, "w", encoding="utf-8") as summary_f:
            json.dump(monitoring_summary, summary_f, indent=2)

        logger.info("Monitoring complete: %d changes detected", len(all_changes))

        return monitoring_summary

    def generate_change_report(self, output_format: str = "markdown") -> str:
        """Generate a human-readable change report."""
        if output_format == "markdown":
            return self._generate_markdown_report()
        elif output_format == "html":
            return self._generate_html_report()
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _generate_markdown_report(self) -> str:
        """Generate markdown change report."""
        lines = [
            f"# Template Monitoring Report - {self.state}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Total URLs monitored: {len(self.snapshots)}",
            f"- Total changes in history: {len(self.change_history)}",
            "",
        ]

        # Recent changes (last 10)
        recent_changes = self.change_history[-10:] if self.change_history else []
        if recent_changes:
            lines.extend(
                [
                    "## Recent Changes",
                    "",
                ]
            )

            for recent_change in reversed(recent_changes):
                severity_icon = (
                    "🔴"
                    if recent_change.severity == "critical"
                    else "🟡" if recent_change.severity == "warning" else "🟢"
                )
                lines.append(
                    f"### {severity_icon} {recent_change.change_type.title()}: {Path(urlparse(recent_change.url).path).name}"
                )
                lines.append(f"- **URL**: {recent_change.url}")
                lines.append(f"- **Description**: {recent_change.description}")
                lines.append(f"- **Detected**: {recent_change.detected_at}")
                lines.append("")

        # Current template status
        lines.extend(
            [
                "## Current Template Status",
                "",
            ]
        )

        for url, snapshots in self.snapshots.items():
            if snapshots:
                latest = snapshots[-1]
                filename = latest.metadata.get("filename", Path(urlparse(url).path).name)
                version = latest.metadata.get("version", "unknown")
                lines.append(f"- **{filename}** (v{version})")
                lines.append(f"  - Last checked: {latest.snapshot_date}")
                lines.append(f"  - Hash: {latest.file_hash[:16]}...")
                lines.append(f"  - Size: {latest.file_size:,} bytes")

        return "\n".join(lines)

    def _generate_html_report(self) -> str:
        """Generate HTML change report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Template Monitoring Report - {self.state}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
                .change {{ margin: 15px 0; padding: 10px; border-left: 4px solid #ccc; }}
                .change.critical {{ border-color: #ff0000; background: #fff0f0; }}
                .change.warning {{ border-color: #ffaa00; background: #fffaf0; }}
                .change.info {{ border-color: #00aa00; background: #f0fff0; }}
                .template {{ margin: 10px 0; padding: 10px; background: #fafafa; }}
            </style>
        </head>
        <body>
            <h1>Template Monitoring Report - {self.state}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <div class="summary">
                <h2>Summary</h2>
                <ul>
                    <li>Total URLs monitored: {len(self.snapshots)}</li>
                    <li>Total changes in history: {len(self.change_history)}</li>
                </ul>
            </div>
        """

        # Recent changes
        recent_changes = self.change_history[-10:] if self.change_history else []
        if recent_changes:
            html += "<h2>Recent Changes</h2>"
            for recent_change in reversed(recent_changes):
                html += f"""
                <div class="change {recent_change.severity}">
                    <h3>{recent_change.change_type.title()}: {Path(urlparse(recent_change.url).path).name}</h3>
                    <p><strong>URL:</strong> {recent_change.url}</p>
                    <p><strong>Description:</strong> {recent_change.description}</p>
                    <p><strong>Detected:</strong> {recent_change.detected_at}</p>
                </div>
                """

        # Current template status
        html += "<h2>Current Template Status</h2>"
        for url, snapshots in self.snapshots.items():
            if snapshots:
                latest = snapshots[-1]
                filename = latest.metadata.get("filename", Path(urlparse(url).path).name)
                version = latest.metadata.get("version", "unknown")
                html += f"""
                <div class="template">
                    <h3>{filename} (v{version})</h3>
                    <ul>
                        <li>Last checked: {latest.snapshot_date}</li>
                        <li>Hash: {latest.file_hash[:16]}...</li>
                        <li>Size: {latest.file_size:,} bytes</li>
                    </ul>
                </div>
                """

        html += "</body></html>"
        return html


def monitor_state_templates(state: str) -> Dict[str, Any]:
    """Convenience function to monitor templates for a state."""
    monitor = TemplateMonitor(state)
    return monitor.run_monitoring()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        state_arg = sys.argv[1]
        print(f"Monitoring templates for {state_arg}...")

        template_monitor = TemplateMonitor(state_arg)
        summary = template_monitor.run_monitoring()

        print("\nMonitoring Summary:")
        print(f"  URLs monitored: {summary['total_urls_monitored']}")
        print(f"  Changes detected: {summary['changes_detected']}")

        if summary["critical_changes"]:
            print("\nCRITICAL CHANGES:")
            for critical_change in summary["critical_changes"]:
                print(f"  - {critical_change['url']}")
                print(f"    {critical_change['description']}")

        # Generate and save report
        report = template_monitor.generate_change_report("markdown")
        report_file = template_monitor.storage_dir / "latest_report.md"
        with open(report_file, "w", encoding="utf-8") as report_f:
            report_f.write(report)
        print(f"\nReport saved to: {report_file}")
    else:
        print("Usage: python -m scrapers.template_monitor <state>")
