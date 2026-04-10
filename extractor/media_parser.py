# extractor/media_parser.py
# Phase 2: File Watcher & Crawler
# This module extracts metadata/text from media files (images, etc.)

from pathlib import Path

from PIL import Image
from config.logger import get_logger
from config.config import GEMINI_API_KEY, GEMINI_VISION_MODEL

logger = get_logger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB limit


def _extract_vision_text(path: Path, img: Image.Image) -> str:
    """Extract text and description using Gemini Vision API."""
    if not GEMINI_API_KEY:
        return ""
        
    try:
        import google.generativeai as genai
        
        # Configure API key
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Use the configured vision model
        model = genai.GenerativeModel(GEMINI_VISION_MODEL)
        
        # Create a prompt for description and OCR
        prompt = (
            "Analyze this image in detail. "
            "1. Provide a comprehensive description of what is in the image. "
            "2. If there is any text (including handwriting, signs, labels, or documents), extract and transcribe all of it exactly as it appears. "
            "3. If it's a handwritten note, specify that it is handwritten."
        )
        
        # Convert image to RGB if it's not (e.g. RGBA) to avoid API issues
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        # Generate content
        response = model.generate_content([prompt, img])
        
        if response.text:
            logger.debug(f"Successfully ran vision analysis for {path}")
            return f"\n--- Image Analysis & OCR ---\n{response.text}"
            
    except ImportError:
        logger.warning("google.generativeai not installed, skipping vision extraction")
    except Exception as e:
        logger.warning(f"Failed to extract vision text for {path}: {e}")
        
    return ""


def parse_media(path: Path) -> str:
    """
    Parse a media file and extract metadata or text content.

    For images, extracts EXIF metadata, dimensions, and format info.
    Also uses Gemini Vision API to extract image description and OCR text.

    Args:
        path: Path to the media file

    Returns:
        Extracted text/metadata as string, or empty string if extraction fails
    """
    if not path.exists():
        logger.warning(f"File does not exist: {path}")
        return ""

    ext = path.suffix.lower()

    # Supported image extensions
    image_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
    }

    if ext not in image_extensions:
        logger.info(f"Skipped file {path} (unsupported media type: {ext})")
        return ""

    try:
        # Check file size
        file_size = path.stat().st_size
        if file_size > MAX_IMAGE_SIZE:
            logger.info(
                f"Skipped file {path} (image too large: {file_size / 1024 / 1024:.1f}MB > 10MB)"
            )
            return ""

        # Open and extract metadata from image
        with Image.open(path) as img:
            text_parts = []

            # Basic file info
            text_parts.append(f"Filename: {path.name}")
            text_parts.append(f"Format: {img.format}")
            text_parts.append(f"Mode: {img.mode}")
            text_parts.append(f"Size: {img.width}x{img.height}")

            # Try to extract EXIF data
            try:
                exif = img.getexif()
                if exif:
                    # Common EXIF tags
                    exif_tags = {
                        271: "Make",
                        272: "Model",
                        306: "DateTime",
                        36867: "DateTimeOriginal",
                        37380: "ExposureBias",
                        37385: "Flash",
                        33434: "ExposureTime",
                        41986: "FocalLength",
                    }

                    for tag_id, tag_name in exif_tags.items():
                        if tag_id in exif:
                            text_parts.append(f"{tag_name}: {exif[tag_id]}")
            except Exception as e:
                logger.debug(f"No EXIF data for {path}: {e}")

            # Try to extract IPTC data (for stock photos, etc.)
            try:
                iptc = img.info.get("IPTC", {})
                if iptc:
                    for key, value in iptc.items():
                        text_parts.append(f"{key}: {value}")
            except Exception:
                pass

            # Extract vision text using Gemini API
            vision_text = _extract_vision_text(path, img)
            if vision_text:
                text_parts.append(vision_text)

            result = "\n".join(text_parts)

            if result:
                logger.debug(f"Successfully extracted metadata from {path}")

            return result

    except Exception as e:
        logger.error(f"Error parsing media file {path}: {e}")
        return ""
