"""CGT Validator - Health cost growth target data validation tool."""

__version__ = "0.1.0"

from .reporters.excel_annotator import ExcelAnnotator
from .reporters.html_reporter import HTMLReporter
from .reporters.markdown_reporter import MarkdownReporter
from .reporters.validation_results import ValidationResults

# Make key components available at package level
from .validators.oregon import OregonValidator

__all__ = [
    "OregonValidator",
    "ValidationResults",
    "HTMLReporter",
    "MarkdownReporter",
    "ExcelAnnotator",
]
