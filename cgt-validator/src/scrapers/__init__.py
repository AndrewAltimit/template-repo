"""CGT Template Web Scraping and Monitoring Tools."""

from .document_downloader import DocumentDownloader, VersionInfo, download_all_documents
from .scheduler import ScrapingScheduler
from .template_monitor import ChangeEvent, TemplateMonitor, TemplateSnapshot, monitor_state_templates
from .web_scraper import DocumentInfo, WebScraper, scrape_state

__all__ = [
    # Web scraper
    "WebScraper",
    "DocumentInfo",
    "scrape_state",
    # Document downloader
    "DocumentDownloader",
    "VersionInfo",
    "download_all_documents",
    # Template monitor
    "TemplateMonitor",
    "TemplateSnapshot",
    "ChangeEvent",
    "monitor_state_templates",
    # Scheduler
    "ScrapingScheduler",
]
