"""Tests for web scraper functionality."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from src.scrapers.web_scraper import DocumentInfo, WebScraper


class TestDocumentInfo:
    """Test DocumentInfo class."""

    def test_document_info_creation(self):
        """Test creating DocumentInfo instance."""
        doc = DocumentInfo(url="https://example.com/test.pdf", title="Test Document", file_type="pdf", version="1.0")

        assert doc.url == "https://example.com/test.pdf"
        assert doc.title == "Test Document"
        assert doc.file_type == "pdf"
        assert doc.version == "1.0"
        assert doc.date_found is not None

    def test_document_info_repr(self):
        """Test DocumentInfo string representation."""
        doc = DocumentInfo(url="https://example.com/test.pdf", title="Test Document", file_type="pdf")

        repr_str = repr(doc)
        assert "DocumentInfo" in repr_str
        assert "Test Document" in repr_str
        assert "pdf" in repr_str


class TestWebScraper:
    """Test WebScraper functionality."""

    def test_scraper_initialization(self, temp_dir: Path):
        """Test WebScraper initialization."""
        scraper = WebScraper("oregon", cache_dir=temp_dir)

        assert scraper.state == "oregon"
        assert scraper.cache_dir == temp_dir
        assert temp_dir.exists()

    def test_extract_version(self):
        """Test version extraction from text."""
        scraper = WebScraper("oregon")

        # Test various version formats
        assert scraper._extract_version("Template v2.0") == "v2.0"
        assert scraper._extract_version("Version 5.1.3") == "Version 5.1.3"  # Case-insensitive match
        assert scraper._extract_version("Manual 2024-03") == "2024-03"
        assert scraper._extract_version("Report 2024") == "2024"
        assert scraper._extract_version("No version here") is None

    def test_is_relevant_link(self):
        """Test link relevance checking."""
        scraper = WebScraper("oregon")
        keywords = ["template", "manual", "2024"]

        # Relevant links
        assert scraper._is_relevant_link("https://example.com/template_2024.pdf", "2024 Template", keywords)
        assert scraper._is_relevant_link("https://example.com/manual.xlsx", "Submission Manual", keywords)

        # Non-relevant links
        assert not scraper._is_relevant_link("https://example.com/page.html", "Some Page", keywords)
        assert not scraper._is_relevant_link("https://example.com/unrelated.pdf", "Unrelated Document", keywords)

    @patch("requests.Session.get")
    def test_fetch_page_success(self, mock_get):
        """Test successful page fetching."""
        mock_response = Mock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        scraper = WebScraper("oregon")
        html = scraper._fetch_page("https://example.com")

        assert html == "<html><body>Test</body></html>"
        mock_get.assert_called_once()

    @patch("requests.Session.get")
    def test_fetch_page_error(self, mock_get):
        """Test page fetching with error."""
        mock_get.side_effect = Exception("Network error")

        scraper = WebScraper("oregon")
        html = scraper._fetch_page("https://example.com")

        assert html is None

    @patch.object(WebScraper, "_fetch_page")
    def test_scrape_index_page(self, mock_fetch, mock_web_response):
        """Test scraping an index page."""
        mock_fetch.return_value = mock_web_response

        scraper = WebScraper("oregon")
        index_config = {
            "url": "https://example.com/index",
            "scan_pattern": r"\.(?:pdf|xlsx)$",
            "keywords": ["template", "manual", "2024"],
        }

        documents = scraper.scrape_index_page(index_config)

        assert len(documents) == 2  # Should find 2 relevant documents
        assert any(doc.title == "Template Version 2" for doc in documents)
        assert any(doc.title == "2024 Manual" for doc in documents)
        assert all(doc.file_type in ["pdf", "xlsx"] for doc in documents)

    @patch.object(WebScraper, "_fetch_page")
    def test_scrape_index_page_no_links(self, mock_fetch):
        """Test scraping page with no relevant links."""
        mock_fetch.return_value = "<html><body>No links here</body></html>"

        scraper = WebScraper("oregon")
        index_config = {"url": "https://example.com/index", "scan_pattern": r"\.pdf$", "keywords": ["template"]}

        documents = scraper.scrape_index_page(index_config)
        assert len(documents) == 0

    @patch.object(WebScraper, "scrape_index_page")
    def test_scrape_all_index_pages(self, mock_scrape, mock_state_config):
        """Test scraping all index pages for a state."""
        # Mock scrape results
        doc1 = DocumentInfo("https://example.com/doc1.pdf", "Doc 1", "pdf")
        doc2 = DocumentInfo("https://example.com/doc2.xlsx", "Doc 2", "xlsx")
        mock_scrape.return_value = [doc1, doc2]

        with patch("src.scrapers.web_scraper.get_state_config") as mock_get_config:
            mock_get_config.return_value = mock_state_config

            scraper = WebScraper("test_state")
            all_docs = scraper.scrape_all_index_pages()

        assert len(all_docs) == 1  # One index URL
        assert len(all_docs["https://example.com/index"]) == 2

    def test_find_latest_templates(self):
        """Test finding latest templates from scraped documents."""
        scraper = WebScraper("oregon")

        # Mock scraped documents
        docs = [
            DocumentInfo("https://example.com/template_v1.pdf", "Template Old", "pdf", version="v1.0"),
            DocumentInfo("https://example.com/template_v2.pdf", "Template New", "pdf", version="v2.0"),
            DocumentInfo("https://example.com/manual_2023.pdf", "Manual Old", "pdf", version="2023"),
            DocumentInfo("https://example.com/manual_2024.pdf", "Manual New", "pdf", version="2024"),
        ]

        with patch.object(scraper, "scrape_all_index_pages") as mock_scrape:
            mock_scrape.return_value = {"test_url": docs}
            latest = scraper.find_latest_templates()

        # Should get latest versions
        assert len(latest) > 0
        versions = [doc.version for doc in latest if doc.version]
        assert "v2.0" in versions or "2024" in versions

    def test_save_results(self, temp_dir: Path):
        """Test saving scraping results."""
        scraper = WebScraper("oregon", cache_dir=temp_dir)

        documents = [
            DocumentInfo("https://example.com/doc1.pdf", "Document 1", "pdf", version="1.0"),
            DocumentInfo("https://example.com/doc2.xlsx", "Document 2", "xlsx", version="2.0"),
        ]

        output_file = temp_dir / "test_results.json"
        scraper.save_results(documents, output_file)

        assert output_file.exists()

        # Load and verify
        with open(output_file) as f:
            data = json.load(f)

        assert data["state"] == "oregon"
        assert len(data["documents"]) == 2
        assert data["documents"][0]["title"] == "Document 1"
        assert data["documents"][1]["version"] == "2.0"
