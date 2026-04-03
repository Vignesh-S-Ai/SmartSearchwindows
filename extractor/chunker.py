# extractor/chunker.py
# Phase 2: File Watcher & Crawler
# This module splits text into overlapping chunks for embedding.

from config.config import CHUNK_SIZE, CHUNK_OVERLAP
from config.logger import get_logger

logger = get_logger(__name__)


def chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks of specified size.

    This function breaks down long text into smaller pieces that can
    be embedded individually. Chunks overlap to maintain context
    at chunk boundaries.

    Args:
        text: The input text to chunk

    Returns:
        List of text chunks
    """
    # Return empty list for empty or whitespace-only text
    if not text or not text.strip():
        return []

    # Return single chunk if text fits within chunk size
    if len(text) <= CHUNK_SIZE:
        return [text]

    # Initialize list to hold chunks
    chunks = []

    # Calculate step size - chunk size minus overlap
    # This determines how much we move forward for each new chunk
    step = CHUNK_SIZE - CHUNK_OVERLAP

    # Iterate through text with the calculated step
    # We use a while loop to handle the step calculation
    start = 0
    while start < len(text):
        # Calculate end position for this chunk
        end = start + CHUNK_SIZE

        # If we're at the end of the text, just take what's left
        if end >= len(text):
            chunk = text[start:]
        else:
            # Otherwise, take the full chunk size
            # This creates overlap with the next chunk
            chunk = text[start:end]

        # Add the chunk to our list if it's not empty
        if chunk.strip():
            chunks.append(chunk)

        # Move start position forward by step amount
        start += step

    # Return the list of chunks (should have at least one element)
    return chunks
