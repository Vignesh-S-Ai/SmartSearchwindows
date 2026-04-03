# watcher/crawler.py
# Phase 2: File Watcher & Crawler
# This module provides the crawler for indexing files.

import time
from pathlib import Path
from typing import Optional

from config.config import WATCH_PATHS, SUPPORTED_EXTENSIONS, IGNORE_DIRS
from config.logger import get_logger
from extractor.document_parser import parse_document
from extractor.media_parser import parse_media
from extractor.chunker import chunk_text

logger = get_logger(__name__)


def _should_skip(path: Path) -> bool:
    """
    Check if a file should be skipped during indexing.

    Returns True if:
    - The path is not a file
    - The file extension is not in SUPPORTED_EXTENSIONS
    - Any part of the path is in IGNORE_DIRS

    Args:
        path: Path to check

    Returns:
        True if the file should be skipped, False otherwise
    """
    # Skip if not a regular file (e.g., directory, symlink)
    if not path.is_file():
        return True

    # Skip if extension is not supported
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return True

    # Skip if any part of the path is in ignore directories
    # Convert path parts to lowercase for case-insensitive comparison
    path_parts = [part.lower() for part in path.parts]
    for ignore_dir in IGNORE_DIRS:
        if ignore_dir.lower() in path_parts:
            return True

    # All checks passed - file should be indexed
    return False


def _extract(path: Path) -> str:
    """
    Extract text content from a file.

    First tries document parsing, then media parsing as fallback.
    Returns empty string if both fail.

    Args:
        path: Path to the file

    Returns:
        Extracted text content as string, or empty string if extraction fails
    """
    # Try document parsing first (handles PDFs, DOCX, text files, etc.)
    try:
        text = parse_document(path)
        if text and text.strip():
            return text
    except Exception as e:
        # Log warning if document parsing fails
        logger.warning(f"Document parsing failed for {path}: {e}")

    # Try media parsing as fallback (handles images with OCR, etc.)
    try:
        text = parse_media(path)
        if text and text.strip():
            return text
    except Exception as e:
        # Log warning if media parsing fails
        logger.warning(f"Media parsing failed for {path}: {e}")

    # Both parsers failed or returned empty - return empty string
    return ""


class Crawler:
    """
    Crawler for indexing files across watched directories.

    This class handles the full indexing pipeline: crawling directories,
    extracting text, chunking, embedding, and storing in indexes.
    """

    def __init__(
        self,
        embedder,
        faiss,
        bm25,
        meta,
    ) -> None:
        """
        Initialize the crawler with index components.

        Args:
            embedder: Embedder instance for generating embeddings
            faiss: FAISSIndex instance for semantic search storage
            bm25: BM25Index instance for keyword search storage
            meta: MetadataStore instance for file metadata storage
        """
        # Store all four components as instance variables
        self.embedder = embedder
        self.faiss = faiss
        self.bm25 = bm25
        self.meta = meta

        logger.info("Crawler initialized")

    def crawl_all(self, paths: Optional[list[Path]] = None) -> None:
        """
        Crawl all specified paths and index their files.

        Walks through each root path recursively and indexes all
        supported files that aren't already indexed.

        Args:
            paths: List of root paths to crawl (defaults to WATCH_PATHS config)
        """
        # Use provided paths or fall back to config
        if paths is None:
            paths = WATCH_PATHS

        # Log the start of crawling with number of root paths
        logger.info(f"Starting crawl of {len(paths)} root paths")

        # Record start time for calculating elapsed time
        start_time = time.time()

        # Counter for indexed files
        indexed_count = 0

        # Loop through each root path
        for root_path in paths:
            # Skip paths that don't exist
            if not root_path.exists():
                logger.warning(f"Root path does not exist: {root_path}")
                continue

            # Use rglob to walk recursively through all files
            # rglob("*") returns all files and directories recursively
            for file_path in root_path.rglob("*"):
                # Skip files that should be ignored
                if _should_skip(file_path):
                    continue

                # Skip files that are already indexed (checks size and mtime)
                if self.meta.is_indexed(file_path):
                    continue

                # Index this file
                self.index_file(file_path)
                indexed_count += 1

        # Calculate elapsed time
        elapsed = time.time() - start_time

        # Log completion with count and elapsed time
        logger.info(f"Crawl complete: indexed {indexed_count} files in {elapsed:.2f}s")

    def index_file(self, path: Path) -> None:
        """
        Index a single file into all indexes.

        This method handles the complete indexing pipeline for one file:
        1. Check if should skip
        2. Extract text content
        3. Chunk the text
        4. Generate embeddings
        5. Add to FAISS index
        6. Add to BM25 index
        7. Store metadata

        Args:
            path: Path to the file to index
        """
        # Check if file should be skipped
        if _should_skip(path):
            return

        try:
            # Extract text content from the file
            text = _extract(path)

            # Return early if no text could be extracted
            if not text or not text.strip():
                logger.debug(f"No text extracted from {path}, skipping")
                return

            # Chunk the text into smaller pieces
            chunks = chunk_text(text)

            # Return early if no chunks were created
            if not chunks:
                logger.debug(f"No chunks created from {path}, skipping")
                return

            # Generate embeddings for all chunks
            vectors = self.embedder.embed_texts(chunks)

            # Filter out chunks where embedding failed (vector is None)
            valid_chunks = []
            valid_vectors = []
            meta_list = []

            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                # Only include chunks with valid embeddings
                if vector is not None:
                    valid_chunks.append(chunk)
                    valid_vectors.append(vector)
                    # Build metadata for this chunk
                    meta_list.append(
                        {
                            "path": str(path),
                            "chunk_idx": i,
                            "text": chunk,
                        }
                    )

            # Add valid vectors to FAISS index for semantic search
            if valid_vectors:
                self.faiss.add(valid_vectors, meta_list)

            # Add valid chunks to BM25 index for keyword search
            if valid_chunks:
                self.bm25.add(valid_chunks, meta_list)

            # Store file metadata in SQLite
            self.meta.upsert(path, chunk_count=len(valid_chunks))

            # Log success with details
            logger.info(
                f"Indexed {path.name}: {len(valid_chunks)} chunks, "
                f"{len(valid_chunks)} embedded"
            )

        except Exception as e:
            # Log error but don't crash - continue with next file
            logger.error(f"Failed to index {path}: {e}")

    def remove_file(self, path: Path) -> None:
        """
        Remove a file from all indexes.

        Removes the file from FAISS, BM25, and metadata store.

        Args:
            path: Path to the file to remove
        """
        try:
            # Remove from FAISS semantic index
            self.faiss.remove_by_path(str(path))

            # Remove from BM25 keyword index
            self.bm25.remove_by_path(str(path))

            # Remove metadata from SQLite
            self.meta.delete(path)

            # Log the removal
            logger.info(f"Removed {path.name} from indexes")

        except Exception as e:
            # Log error but don't crash
            logger.error(f"Failed to remove {path}: {e}")

    def reindex_file(self, path: Path) -> None:
        """
        Reindex a file (remove and index again).

        Convenience method that first removes the old index entries,
        then indexes the file fresh.

        Args:
            path: Path to the file to reindex
        """
        # First remove old entries
        self.remove_file(path)

        # Then index fresh
        self.index_file(path)
