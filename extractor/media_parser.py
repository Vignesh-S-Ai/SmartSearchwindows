# extractor/media_parser.py
# Phase 2: File Watcher & Crawler
# This module extracts metadata/text from media files (images, etc.)

from pathlib import Path
from config.logger import get_logger

logger = get_logger(__name__)


def parse_media(path: Path) -> str:
    """
    Parse a media file and extract metadata or text content.

    This function attempts to extract information from media files.
    For images, it could extract EXIF data or perform OCR.
    Currently returns empty string as placeholder.

    Args:
        path: Path to the media file

    Returns:
        Extracted text/metadata as string, or empty string if extraction fails
    """
    # Get the file extension in lowercase for consistent comparison
    ext = path.suffix.lower()

    try:
        # TODO: Implement actual media parsing for each supported format

        # Image files - could use PIL for EXIF, or pytesseract for OCR
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            pass

        # Return empty string - no actual parsing implemented yet
        return ""

    except Exception as e:
        # Log any errors during parsing
        logger.warning(f"Failed to parse media {path}: {e}")
        return ""
