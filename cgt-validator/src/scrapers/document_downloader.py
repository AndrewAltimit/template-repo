"""Document downloader with version tracking and change detection."""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from tqdm import tqdm

from config.states_config import get_state_config

from .web_scraper import DocumentInfo, WebScraper


class VersionInfo:
    """Information about a document version."""

    def __init__(self, url: str, version: str, checksum: str, file_size: int, download_date: str):
        self.url = url
        self.version = version
        self.checksum = checksum
        self.file_size = file_size
        self.download_date = download_date

    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "version": self.version,
            "checksum": self.checksum,
            "file_size": self.file_size,
            "download_date": self.download_date,
        }


class DocumentDownloader:
    """Downloads documents with version tracking and change detection."""

    def __init__(self, state_name: str, storage_dir: Optional[Path] = None):
        self.state = state_name
        self.config = get_state_config(state_name)
        self.storage_dir = storage_dir or Path(f"./states/{state_name}")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Version tracking file
        self.version_file = self.storage_dir / "version_history.json"
        self.version_history = self._load_version_history()

        # Set up session
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 CGT-Validator/1.0"})

    def _load_version_history(self) -> Dict:
        """Load version history from file."""
        if self.version_file.exists():
            with open(self.version_file, "r", encoding="utf-8") as f:
                return dict(json.load(f))
        return {}

    def _save_version_history(self):
        """Save version history to file."""
        with open(self.version_file, "w", encoding="utf-8") as f:
            json.dump(self.version_history, f, indent=2)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _download_file(self, url: str, dest_path: Path) -> Tuple[bool, int]:
        """Download a file with progress bar. Returns (success, file_size)."""
        try:
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            with open(dest_path, "wb") as f:
                with tqdm(total=total_size, unit="B", unit_scale=True, desc=dest_path.name) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            return True, dest_path.stat().st_size
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error downloading {url}: {e}")
            if dest_path.exists():
                dest_path.unlink()
            return False, 0

    def _get_document_path(self, url: str, document_type: str, version: Optional[str] = None) -> Path:
        """Generate path for storing a document."""
        # Extract filename from URL
        filename = Path(url).name
        if not filename or filename == "/":
            filename = f"document_{hashlib.md5(url.encode()).hexdigest()[:8]}"

        # Create subdirectory structure
        year = datetime.now().year
        type_dir = self.storage_dir / str(year) / document_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Add version to filename if provided
        if version:
            name_parts = filename.rsplit(".", 1)
            if len(name_parts) == 2:
                filename = f"{name_parts[0]}_{version}.{name_parts[1]}"
            else:
                filename = f"{filename}_{version}"

        return type_dir / filename

    def check_for_updates(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check if a document has been updated. Returns (has_update, current_version)."""
        # Try to get file info without downloading
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            response.raise_for_status()

            # Get file size and last modified
            file_size = int(response.headers.get("content-length", 0))
            last_modified = response.headers.get("last-modified", "")

            # Create a version string from available info
            current_version = f"{last_modified}_{file_size}"

            # Check against history
            if url in self.version_history:
                last_version = self.version_history[url][-1]
                if last_version.get("file_size") != file_size:
                    return True, current_version

            return False, current_version

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error checking {url}: {e}")
            return False, None

    def download_direct_urls(self) -> List[Tuple[str, Path]]:
        """Download all direct URLs (List A) for the state."""
        downloaded = []

        print(f"\nDownloading direct URLs for {self.state}...")
        for url_config in self.config["direct_urls"]:
            url = url_config["url"]
            document_type = url_config["type"]

            # Check for updates
            has_update, version = self.check_for_updates(url)

            # Determine if we need to download
            need_download = True
            if url in self.version_history and not has_update:
                print(f"  {url_config['description']}: No updates detected")
                need_download = False

            if need_download:
                # Download the file
                dest_path = self._get_document_path(url, document_type, version)
                success, file_size = self._download_file(url, dest_path)

                if success:
                    # Calculate checksum
                    checksum = self._calculate_checksum(dest_path)

                    # Update version history
                    version_info = VersionInfo(
                        url=url,
                        version=version or url_config.get("version", "unknown"),
                        checksum=checksum,
                        file_size=file_size,
                        download_date=datetime.now().isoformat(),
                    )

                    if url not in self.version_history:
                        self.version_history[url] = []
                    self.version_history[url].append(version_info.to_dict())

                    downloaded.append((url, dest_path))
                    print(f"  Downloaded: {url_config['description']} -> {dest_path}")

        self._save_version_history()
        return downloaded

    def download_scraped_documents(self, documents: List[DocumentInfo]) -> List[Tuple[str, Path]]:
        """Download documents found by web scraper."""
        downloaded = []

        print(f"\nDownloading scraped documents for {self.state}...")
        for doc in tqdm(documents, desc="Downloading"):
            url = doc.url

            # Check if we already have this document
            if url in self.version_history:
                # Check for updates
                has_update, _ = self.check_for_updates(url)
                if not has_update:
                    print(f"  Skipping {doc.title}: Already downloaded")
                    continue

            # Download the document
            dest_path = self._get_document_path(url, doc.file_type, doc.version)
            success, file_size = self._download_file(url, dest_path)

            if success:
                # Calculate checksum
                checksum = self._calculate_checksum(dest_path)

                # Update version history
                version_info = VersionInfo(
                    url=url,
                    version=doc.version or "unknown",
                    checksum=checksum,
                    file_size=file_size,
                    download_date=datetime.now().isoformat(),
                )

                if url not in self.version_history:
                    self.version_history[url] = []
                self.version_history[url].append(version_info.to_dict())

                downloaded.append((url, dest_path))

            # Rate limiting
            time.sleep(1)

        self._save_version_history()
        return downloaded

    def archive_old_versions(self):
        """Move old versions to archive directory."""
        archive_dir = self.storage_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        # Find files to archive
        for year_dir in self.storage_dir.glob("*/"):
            if year_dir.name == "archive":
                continue

            for type_dir in year_dir.glob("*/"):
                for file_path in type_dir.glob("*"):
                    # Check if this is an old version
                    # (Simple logic: if filename contains version and it's not the latest)
                    if "_v" in file_path.name or "_20" in file_path.name:
                        # Move to archive
                        archive_path = archive_dir / file_path.name
                        file_path.rename(archive_path)
                        print(f"Archived: {file_path.name}")

    def get_latest_documents(self) -> Dict[str, Path]:
        """Get paths to the latest version of each document type."""
        latest = {}

        # Walk through storage directory
        for year_dir in sorted(self.storage_dir.glob("*/"), reverse=True):
            if year_dir.name == "archive":
                continue

            for type_dir in year_dir.glob("*/"):
                for file_path in sorted(type_dir.glob("*"), reverse=True):
                    doc_key = f"{type_dir.name}_{file_path.stem}"
                    if doc_key not in latest:
                        latest[doc_key] = file_path

        return latest


def download_all_documents(state_name: str) -> Dict[str, Path]:
    """Download all documents for a state (both direct URLs and scraped)."""
    downloader = DocumentDownloader(state_name)

    # Download direct URLs
    downloader.download_direct_urls()

    # Scrape and download from index pages
    scraper = WebScraper(state)
    scraped_docs = scraper.find_latest_templates()
    downloader.download_scraped_documents(scraped_docs)

    # Archive old versions
    downloader.archive_old_versions()

    # Return latest documents
    return downloader.get_latest_documents()


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        state = sys.argv[1]
        print(f"Downloading all documents for {state}...")
        latest_docs = download_all_documents(state)

        print(f"\nLatest documents for {state}:")
        for doc_type, path in latest_docs.items():
            print(f"  {doc_type}: {path}")
    else:
        print("Usage: python -m scrapers.document_downloader <state>")
        print("Example: python -m scrapers.document_downloader oregon")
