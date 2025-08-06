"""Web scraper for finding and downloading CGT templates from state websites."""

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from config.states_config import IndexURLConfig, get_state_config


class DocumentInfo:
    """Information about a discovered document."""

    def __init__(self, url: str, title: str, file_type: str, date_found: Optional[str] = None, version: Optional[str] = None):
        self.url = url
        self.title = title
        self.file_type = file_type
        self.date_found = date_found or datetime.now().strftime("%Y-%m-%d")
        self.version = version

    def __repr__(self):
        return f"DocumentInfo(title='{self.title}', type='{self.file_type}', url='{self.url}')"


class WebScraper:
    """Scraper for finding CGT templates and documents from state websites."""

    def __init__(self, state_name: str, cache_dir: Optional[Path] = None):
        self.state = state_name
        self.config = get_state_config(state_name)
        self.cache_dir = cache_dir or Path(f"./cache/{state_name}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Set up session with headers
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CGT-Validator/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        # Rate limiting
        self.min_delay = 1.0  # Minimum seconds between requests
        self.last_request_time = 0

    def _rate_limit(self):
        """Implement rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with error handling and rate limiting."""
        self._rate_limit()

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except (requests.RequestException, OSError, ValueError) as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _extract_version(self, text: str) -> Optional[str]:
        """Extract version number from text."""
        # Look for common version patterns
        patterns = [
            r"v(\d+(?:\.\d+)*)",  # v1.0, v2.5.1
            r"version\s*(\d+(?:\.\d+)*)",  # version 5.0
            r"(\d{4})-(\d{2})",  # 2024-01 (year-month)
            r"(\d{4})",  # Just year
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _is_relevant_link(self, url: str, text: str, keywords: List[str]) -> bool:
        """Check if a link is relevant based on URL and text content."""
        # Check file extension
        if not re.search(r"\.(?:xlsx?|xlsm|pdf|docx?|zip)$", url, re.IGNORECASE):
            return False

        # Check keywords in URL and text
        combined_text = f"{url} {text}".lower()
        return any(keyword.lower() in combined_text for keyword in keywords)

    def scrape_index_page(self, index_config: IndexURLConfig) -> List[DocumentInfo]:
        """Scrape an index page for document links."""
        print(f"Scraping: {index_config['url']}")

        html = self._fetch_page(index_config["url"])
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        base_url = index_config["url"]
        documents = []
        seen_urls: Set[str] = set()

        # Find all links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)

            # Make URL absolute
            full_url = urljoin(base_url, href)

            # Skip if already seen
            if full_url in seen_urls:
                continue

            # Check if link is relevant
            if self._is_relevant_link(full_url, text, index_config["keywords"]):
                seen_urls.add(full_url)

                # Extract file type
                file_match = re.search(r"\.([a-zA-Z0-9]+)$", full_url)
                file_type = file_match.group(1).lower() if file_match else "unknown"

                # Extract version if possible
                version = self._extract_version(text) or self._extract_version(full_url)

                # Create document info
                doc_info = DocumentInfo(
                    url=full_url, title=text or Path(urlparse(full_url).path).name, file_type=file_type, version=version
                )
                documents.append(doc_info)

        print(f"Found {len(documents)} relevant documents")
        return documents

    def scrape_all_index_pages(self) -> Dict[str, List[DocumentInfo]]:
        """Scrape all index pages for the state."""
        all_documents = {}

        for index_config in tqdm(self.config["index_urls"], desc=f"Scraping {self.state} sites"):
            documents = self.scrape_index_page(index_config)
            all_documents[index_config["url"]] = documents

        return all_documents

    def find_latest_templates(self) -> List[DocumentInfo]:
        """Find the latest version of templates from all scraped documents."""
        all_docs = self.scrape_all_index_pages()

        # Flatten all documents
        documents = []
        for doc_list in all_docs.values():
            documents.extend(doc_list)

        # Group by file type and title similarity
        latest_docs = []
        processed_titles = set()

        # Sort by version (if available) to get latest
        documents.sort(key=lambda d: d.version or "0", reverse=True)

        for doc_item in documents:
            # Simple deduplication based on title similarity
            base_title = re.sub(r"[^a-zA-Z0-9]+", "", doc_item.title.lower())
            if base_title not in processed_titles:
                processed_titles.add(base_title)
                latest_docs.append(doc_item)

        return latest_docs

    def save_results(self, documents: List[DocumentInfo], output_file: Optional[Path] = None):
        """Save scraping results to a JSON file."""
        import json

        output_file = output_file or self.cache_dir / f"scraped_documents_{datetime.now().strftime('%Y%m%d')}.json"

        data = {
            "state": self.state,
            "scrape_date": datetime.now().isoformat(),
            "documents": [
                {
                    "url": doc.url,
                    "title": doc.title,
                    "file_type": doc.file_type,
                    "version": doc.version,
                    "date_found": doc.date_found,
                }
                for doc in documents
            ],
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"Results saved to: {output_file}")


def scrape_state(state_name: str) -> List[DocumentInfo]:
    """Convenience function to scrape all documents for a state."""
    scraper = WebScraper(state_name)
    documents = scraper.find_latest_templates()
    scraper.save_results(documents)
    return documents


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        state = sys.argv[1]
        print(f"Scraping documents for {state}...")
        docs = scrape_state(state)
        print(f"\nFound {len(docs)} documents:")
        for doc in docs:
            print(f"  - {doc.title} ({doc.file_type})")
            print(f"    URL: {doc.url}")
            if doc.version:
                print(f"    Version: {doc.version}")
    else:
        print("Usage: python -m scrapers.web_scraper <state>")
        print("Example: python -m scrapers.web_scraper oregon")
