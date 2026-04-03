# extractor/document_parser.py
# Phase 2: File Watcher & Crawler
# This module parses various document formats (PDF, DOCX, TXT, etc.)

from pathlib import Path
from config.logger import get_logger

logger = get_logger(__name__)


def parse_document(path: Path) -> str:
    """
    Parse a document file and extract text content.

    This function attempts to extract text from various document formats.
    It currently returns an empty string as a placeholder - the actual
    implementation would use libraries like PyPDF2, python-docx, etc.

    Args:
        path: Path to the document file

    Returns:
        Extracted text content as string, or empty string if extraction fails
    """
    # Get the file extension in lowercase for consistent comparison
    ext = path.suffix.lower()

    try:
        # TODO: Implement actual document parsing for each supported format
        # For now, return empty string to indicate parsing not implemented

        # PDF files - use PyPDF2 or pdfplumber
        if ext == ".pdf":
            pass

        # DOCX files - use python-docx
        elif ext in (".docx", ".doc"):
            pass

        # PowerPoint files - use python-pptx
        elif ext == ".pptx":
            pass

        # Excel files - use openpyxl
        elif ext == ".xlsx":
            pass

        # CSV files - use pandas or csv module
        elif ext == ".csv":
            pass

        # Text-based formats - can read directly
        elif ext in (
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".html",
            ".css",
            ".json",
            ".yaml",
            ".yml",
        ):
            # For text files, we can read directly
            # This will be handled by the fallback in _extract
            pass

        # Return empty string - no actual parsing implemented yet
        return ""

    except Exception as e:
        # Log any errors during parsing
        logger.warning(f"Failed to parse document {path}: {e}")
        return ""
