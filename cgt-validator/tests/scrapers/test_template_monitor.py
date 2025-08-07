"""Tests for template monitoring functionality."""

import hashlib
from pathlib import Path
from unittest.mock import Mock, patch

from src.scrapers.template_monitor import ChangeEvent, TemplateMonitor, TemplateSnapshot, monitor_state_templates


class TestTemplateSnapshot:
    """Test TemplateSnapshot class."""

    def test_snapshot_creation(self):
        """Test creating a template snapshot."""
        snapshot = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="abc123def456",
            file_size=1024,
            content_hash="xyz789",
            metadata={"version": "2.0"},
        )

        assert snapshot.url == "https://example.com/template.xlsx"
        assert snapshot.file_hash == "abc123def456"
        assert snapshot.file_size == 1024
        assert snapshot.content_hash == "xyz789"
        assert snapshot.metadata["version"] == "2.0"
        assert snapshot.snapshot_date is not None

    def test_snapshot_serialization(self):
        """Test snapshot to_dict and from_dict methods."""
        original = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="abc123",
            file_size=2048,
            content_hash="def456",
            metadata={"title": "Test Template"},
            snapshot_date="2024-01-01T12:00:00",
        )

        # Serialize to dict
        data = original.to_dict()
        assert data["url"] == "https://example.com/template.xlsx"
        assert data["file_hash"] == "abc123"
        assert data["file_size"] == 2048

        # Deserialize from dict
        restored = TemplateSnapshot.from_dict(data)
        assert restored.url == original.url
        assert restored.file_hash == original.file_hash
        assert restored.file_size == original.file_size
        assert restored.content_hash == original.content_hash
        assert restored.metadata == original.metadata
        assert restored.snapshot_date == original.snapshot_date


class TestChangeEvent:
    """Test ChangeEvent class."""

    def test_change_event_creation(self):
        """Test creating a change event."""
        old_snapshot = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="old_hash",
            file_size=1000,
        )
        new_snapshot = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="new_hash",
            file_size=1500,
        )

        event = ChangeEvent(
            url="https://example.com/template.xlsx",
            change_type="modified",
            old_snapshot=old_snapshot,
            new_snapshot=new_snapshot,
            description="File size increased",
            severity="warning",
        )

        assert event.url == "https://example.com/template.xlsx"
        assert event.change_type == "modified"
        assert event.old_snapshot == old_snapshot
        assert event.new_snapshot == new_snapshot
        assert event.description == "File size increased"
        assert event.severity == "warning"
        assert event.detected_at is not None

    def test_change_event_serialization(self):
        """Test change event serialization."""
        snapshot = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="hash123",
            file_size=1000,
        )

        event = ChangeEvent(
            url="https://example.com/template.xlsx",
            change_type="new",
            old_snapshot=None,
            new_snapshot=snapshot,
            description="New template discovered",
            severity="info",
        )

        data = event.to_dict()
        assert data["url"] == "https://example.com/template.xlsx"
        assert data["change_type"] == "new"
        assert data["old_snapshot"] is None
        assert data["new_snapshot"] is not None
        assert data["description"] == "New template discovered"
        assert data["severity"] == "info"


class TestTemplateMonitor:
    """Test TemplateMonitor functionality."""

    def test_monitor_initialization(self, temp_dir: Path):
        """Test TemplateMonitor initialization."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        assert monitor.state == "oregon"
        assert monitor.storage_dir == temp_dir
        assert monitor.snapshots_file.exists()
        assert monitor.changes_file.exists()
        assert monitor.monitoring_config_file.exists()

    def test_calculate_file_hash(self, temp_dir: Path):
        """Test file hash calculation."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        # Create a test file
        test_file = temp_dir / "test.txt"
        test_content = b"Test content for hashing"
        test_file.write_bytes(test_content)

        # Calculate hash
        file_hash = monitor._calculate_file_hash(test_file)

        # Verify hash
        expected_hash = hashlib.sha256(test_content).hexdigest()
        assert file_hash == expected_hash

    def test_extract_text_from_pdf(self, temp_dir: Path):
        """Test text extraction from PDF files."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)
        monitor.monitoring_config["extract_text_from_pdfs"] = True

        # Create test PDF file
        test_pdf = temp_dir / "test.pdf"
        test_pdf.write_bytes(b"PDF content")

        # Mock PyPDF2 inside the method
        with patch("PyPDF2.PdfReader") as mock_reader_class:
            mock_reader = Mock()
            mock_page = Mock()
            mock_page.extract_text.return_value = "Test PDF content"
            mock_reader.pages = [mock_page]
            mock_reader_class.return_value = mock_reader

            # Extract text
            text = monitor._extract_text_content(test_pdf)

            assert text == "Test PDF content"
            mock_reader_class.assert_called_once()

    def test_extract_text_from_text_file(self, temp_dir: Path):
        """Test text extraction from text files."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        # Create test text file
        test_file = temp_dir / "test.txt"
        test_content = "Test text content\nWith multiple lines"
        test_file.write_text(test_content)

        # Extract text
        text = monitor._extract_text_content(test_file)

        assert text == test_content

    def test_extract_text_from_excel(self, temp_dir: Path):
        """Test text extraction from Excel files."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)
        monitor.monitoring_config["extract_text_from_pdfs"] = True

        # Create test Excel file
        test_excel = temp_dir / "test.xlsx"
        test_excel.write_bytes(b"Excel content")

        # Mock openpyxl inside the method
        with patch("openpyxl.load_workbook") as mock_load_wb:
            mock_wb = Mock()
            mock_sheet = Mock()
            mock_sheet.iter_rows.return_value = [
                ("A1", "B1", None),
                ("A2", None, "C2"),
            ]
            mock_wb.worksheets = [mock_sheet]
            mock_load_wb.return_value = mock_wb

            # Extract text
            text = monitor._extract_text_content(test_excel)

            assert text is not None
            assert "A1 B1" in text
            assert "A2 C2" in text

    def test_detect_field_changes(self, temp_dir: Path):
        """Test detection of field changes in text."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)
        monitor.monitoring_config["track_field_changes"] = True
        monitor.monitoring_config["critical_fields"] = ["PROV_ID", "MEMBER_MONTHS"]

        old_text = """
        PROV_ID: 12345
        MEMBER_MONTHS: 1000
        OTHER_FIELD: ABC
        """

        new_text = """
        PROV_ID: 67890
        MEMBER_MONTHS: 1000
        OTHER_FIELD: XYZ
        """

        changed_fields = monitor._detect_field_changes(old_text, new_text)

        assert "PROV_ID" in changed_fields
        assert "MEMBER_MONTHS" not in changed_fields

    def test_compare_snapshots_no_change(self, temp_dir: Path):
        """Test comparing identical snapshots."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        snapshot1 = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="same_hash",
            file_size=1000,
        )
        snapshot2 = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="same_hash",
            file_size=1000,
        )

        changed, description, severity = monitor._compare_snapshots(snapshot1, snapshot2)

        assert not changed
        assert description == ""
        assert severity == "info"

    def test_compare_snapshots_with_changes(self, temp_dir: Path):
        """Test comparing different snapshots."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        snapshot1 = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="old_hash",
            file_size=1000,
            metadata={"version": "1.0"},
        )
        snapshot2 = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="new_hash",
            file_size=2000,
            metadata={"version": "2.0"},
        )

        changed, description, severity = monitor._compare_snapshots(snapshot1, snapshot2)

        assert changed
        assert "size change" in description.lower()
        assert "version changed" in description.lower()
        assert severity == "warning"  # Size change alone is warning now

    @patch("requests.Session.get")
    def test_download_and_snapshot(self, mock_get, temp_dir: Path):
        """Test downloading and creating a snapshot."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        # Mock response
        mock_response = Mock()
        mock_response.content = b"Test file content"
        mock_response.headers = {
            "content-type": "application/pdf",
            "last-modified": "2024-01-01",
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Download and snapshot
        snapshot = monitor._download_and_snapshot("https://example.com/test.pdf")

        assert snapshot is not None
        assert snapshot.url == "https://example.com/test.pdf"
        assert snapshot.file_size == len(b"Test file content")
        assert snapshot.metadata["content_type"] == "application/pdf"

    @patch.object(TemplateMonitor, "_download_and_snapshot")
    def test_monitor_direct_urls(self, mock_download, temp_dir: Path):
        """Test monitoring direct URLs."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)
        monitor.monitoring_config["monitor_direct_urls"] = True

        # Override config for test
        monitor.config = {
            "direct_urls": [
                {
                    "url": "https://example.com/manual.pdf",
                    "type": "pdf",
                    "description": "Test Manual",
                }
            ],
            "index_urls": [],
        }

        # Mock snapshot
        new_snapshot = TemplateSnapshot(
            url="https://example.com/manual.pdf",
            file_hash="new_hash",
            file_size=5000,
        )
        mock_download.return_value = new_snapshot

        # Run monitoring
        changes = monitor.monitor_direct_urls()

        assert len(changes) == 1
        assert changes[0].change_type == "new"
        assert changes[0].url == "https://example.com/manual.pdf"

    @patch.object(TemplateMonitor, "_download_and_snapshot")
    def test_monitor_scraped_templates(self, mock_download, temp_dir: Path):
        """Test monitoring scraped templates."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)
        monitor.monitoring_config["monitor_scraped_templates"] = True

        # Mock scraped documents
        from src.scrapers.web_scraper import DocumentInfo

        # Mock the scraper's find_latest_templates method directly
        with patch.object(monitor.scraper, "find_latest_templates") as mock_find:
            mock_find.return_value = [
                DocumentInfo(
                    url="https://example.com/template.xlsx",
                    title="Test Template",
                    file_type="xlsx",
                    version="2.0",
                )
            ]

            # Mock snapshot
            new_snapshot = TemplateSnapshot(
                url="https://example.com/template.xlsx",
                file_hash="template_hash",
                file_size=10000,
            )
            mock_download.return_value = new_snapshot

            # Run monitoring
            changes = monitor.monitor_scraped_templates()

            assert len(changes) == 1
            assert changes[0].change_type == "new"
            assert "Test Template" in changes[0].description

    def test_generate_markdown_report(self, temp_dir: Path):
        """Test generating markdown report."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        # Add some test data
        snapshot = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="test_hash",
            file_size=5000,
            metadata={"filename": "template.xlsx", "version": "2.0"},
        )
        monitor.snapshots["https://example.com/template.xlsx"] = [snapshot]

        change = ChangeEvent(
            url="https://example.com/template.xlsx",
            change_type="modified",
            old_snapshot=None,
            new_snapshot=snapshot,
            description="Template updated",
            severity="warning",
        )
        monitor.change_history = [change]

        # Generate report
        report = monitor._generate_markdown_report()

        assert "# Template Monitoring Report - oregon" in report
        assert "template.xlsx" in report
        assert "Template updated" in report
        assert "🟡" in report  # Warning icon

    def test_generate_html_report(self, temp_dir: Path):
        """Test generating HTML report."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        # Add some test data
        snapshot = TemplateSnapshot(
            url="https://example.com/template.xlsx",
            file_hash="test_hash",
            file_size=5000,
            metadata={"filename": "template.xlsx", "version": "2.0"},
        )
        monitor.snapshots["https://example.com/template.xlsx"] = [snapshot]

        # Generate report
        report = monitor._generate_html_report()

        assert "<title>Template Monitoring Report - oregon</title>" in report
        assert "template.xlsx" in report
        assert "v2.0" in report

    @patch.object(TemplateMonitor, "monitor_direct_urls")
    @patch.object(TemplateMonitor, "monitor_scraped_templates")
    def test_run_monitoring(self, mock_scraped, mock_direct, temp_dir: Path):
        """Test running complete monitoring cycle."""
        monitor = TemplateMonitor("oregon", storage_dir=temp_dir)

        # Mock changes
        change1 = ChangeEvent(
            url="https://example.com/direct.pdf",
            change_type="new",
            old_snapshot=None,
            new_snapshot=None,
            description="New direct URL",
            severity="info",
        )
        change2 = ChangeEvent(
            url="https://example.com/scraped.xlsx",
            change_type="modified",
            old_snapshot=None,
            new_snapshot=None,
            description="Template modified",
            severity="critical",
        )

        mock_direct.return_value = [change1]
        mock_scraped.return_value = [change2]

        # Run monitoring
        summary = monitor.run_monitoring()

        assert summary["state"] == "oregon"
        assert summary["changes_detected"] == 2
        assert summary["changes_by_type"]["new"] == 1
        assert summary["changes_by_type"]["modified"] == 1
        assert summary["changes_by_severity"]["info"] == 1
        assert summary["changes_by_severity"]["critical"] == 1
        assert len(summary["critical_changes"]) == 1

    def test_monitoring_config_persistence(self, temp_dir: Path):
        """Test that monitoring configuration is saved and loaded correctly."""
        # Create monitor with custom config
        monitor1 = TemplateMonitor("oregon", storage_dir=temp_dir)
        monitor1.monitoring_config["monitor_direct_urls"] = False
        monitor1.monitoring_config["critical_fields"] = ["CUSTOM_FIELD"]
        monitor1._save_monitoring_config()

        # Create new monitor instance
        monitor2 = TemplateMonitor("oregon", storage_dir=temp_dir)

        # Check config was loaded
        assert monitor2.monitoring_config["monitor_direct_urls"] is False
        assert "CUSTOM_FIELD" in monitor2.monitoring_config["critical_fields"]


def test_monitor_state_templates(temp_dir: Path):
    """Test the convenience function for monitoring state templates."""
    with patch("src.scrapers.template_monitor.TemplateMonitor") as mock_monitor_class:
        mock_monitor = Mock()
        mock_monitor.run_monitoring.return_value = {
            "state": "oregon",
            "changes_detected": 3,
        }
        mock_monitor_class.return_value = mock_monitor

        result = monitor_state_templates("oregon")

        assert result["state"] == "oregon"
        assert result["changes_detected"] == 3
        mock_monitor.run_monitoring.assert_called_once()
