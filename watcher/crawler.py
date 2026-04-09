# watcher/crawler.py
# Phase 2: File Watcher & Crawler
# This module provides the crawler for indexing files.

import hashlib
import time
from pathlib import Path
from typing import Optional

from config.config import WATCH_PATHS, SUPPORTED_EXTENSIONS, IGNORE_DIRS
from config.logger import get_logger
from extractor.document_parser import parse_document
from extractor.media_parser import parse_media
from extractor.chunker import chunk_text

logger = get_logger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit


class CrawlerStats:
    """Track crawling statistics for logging."""

    def __init__(self):
        self.discovered = 0
        self.indexed = 0
        self.skipped_no_ext = 0
        self.skipped_ignore_dir = 0
        self.skipped_too_large = 0
        self.skipped_empty = 0
        self.skipped_already_indexed = 0
        self.skipped_no_content = 0
        self.errors = 0

    def summary(self) -> str:
        return (
            f"Discovered: {self.discovered}, "
            f"Indexed: {self.indexed}, "
            f"Skipped (no ext): {self.skipped_no_ext}, "
            f"Skipped (ignore dir): {self.skipped_ignore_dir}, "
            f"Skipped (too large): {self.skipped_too_large}, "
            f"Skipped (empty): {self.skipped_empty}, "
            f"Skipped (already indexed): {self.skipped_already_indexed}, "
            f"Skipped (no content): {self.skipped_no_content}, "
            f"Errors: {self.errors}"
        )


# Global stats instance
_stats = CrawlerStats()


def _compute_file_hash(path: Path) -> str:
    """Compute MD5 hash of file for duplicate detection."""
    try:
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.debug(f"Could not compute hash for {path}: {e}")
        return ""


def _should_skip(path: Path) -> tuple[bool, str]:
    """
    Check if a file should be skipped during indexing.

    Returns:
        Tuple of (should_skip: bool, reason: str)
    """
    # Skip if not a regular file (e.g., directory, symlink)
    if not path.is_file():
        return True, "not a regular file"

    # Skip if extension is not supported
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return True, f"unsupported type: {path.suffix}"

    # Skip if any part of the path is in ignore directories
    path_parts = [part.lower() for part in path.parts]
    for ignore_dir in IGNORE_DIRS:
        if ignore_dir.lower() in path_parts:
            return True, f"in ignore directory: {ignore_dir}"

    # Skip if file is too large
    try:
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return True, f"too large: {file_size / 1024 / 1024:.1f}MB"
        if file_size == 0:
            return True, "empty file"
    except Exception as e:
        return True, f"cannot access: {e}"

    # All checks passed - file should be indexed
    return False, ""


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
    text = ""

    # Try document parsing first (handles PDFs, DOCX, text files, etc.)
    try:
        text = parse_document(path)
        if text and text.strip():
            return text
    except Exception as e:
        logger.warning(f"Document parsing failed for {path}: {e}")

    # Try media parsing as fallback (handles images with metadata, etc.)
    try:
        text = parse_media(path)
        if text and text.strip():
            return text
    except Exception as e:
        logger.warning(f"Media parsing failed for {path}: {e}")

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
        self.embedder = embedder
        self.faiss = faiss
        self.bm25 = bm25
        self.meta = meta

        logger.info("Crawler initialized")

    def crawl_all(self, paths: Optional[list[Path]] = None, force: bool = False) -> int:
        """
        Crawl all specified paths and index their files.

        Walks through each root path recursively and indexes all
        supported files that aren't already indexed.

        Args:
            paths: List of root paths to crawl (defaults to WATCH_PATHS config)
            force: If True, re-index all files ignoring previous index state

        Returns:
            Number of files indexed
        """
        global _stats

        # Reset stats for this crawl
        _stats = CrawlerStats()

        if paths is None:
            paths = WATCH_PATHS

        logger.info(
            f"Starting crawl of {len(paths)} root paths: {[str(p) for p in paths]}"
        )

        start_time = time.time()

        for root_path in paths:
            if not root_path.exists():
                logger.warning(f"Root path does not exist: {root_path}")
                continue

            logger.info(f"Scanning directory: {root_path}")

            # Use rglob to walk recursively through all files
            for file_path in root_path.rglob("*"):
                _stats.discovered += 1

                # Check if should skip
                should_skip, reason = _should_skip(file_path)
                if should_skip:
                    if "unsupported type" in reason:
                        _stats.skipped_no_ext += 1
                    elif "ignore directory" in reason:
                        _stats.skipped_ignore_dir += 1
                    elif "too large" in reason:
                        _stats.skipped_too_large += 1
                    elif "empty file" in reason:
                        _stats.skipped_empty += 1
                    else:
                        _stats.skipped_no_ext += 1

                    logger.debug(f"Skipped file {file_path} ({reason})")
                    continue

                # Log discovered file
                if _stats.discovered % 100 == 0:
                    logger.info(f"Discovered {_stats.discovered} files so far...")

                # Check if already indexed (skip unless force=True)
                if not force and self.meta.is_indexed(file_path):
                    _stats.skipped_already_indexed += 1
                    logger.debug(f"Skipped file {file_path} (already indexed)")
                    continue

                # Index this file
                try:
                    self.index_file(file_path)
                    _stats.indexed += 1
                except Exception as e:
                    _stats.errors += 1
                    logger.error(f"Error indexing {file_path}: {e}")

        elapsed = time.time() - start_time

        logger.info(f"Crawl complete: {_stats.summary()}")
        logger.info(f"Total time: {elapsed:.2f}s")

        return _stats.indexed

    def index_file(self, path: Path) -> bool:
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

        Returns:
            True if file was indexed successfully, False otherwise
        """
        should_skip, reason = _should_skip(path)
        if should_skip:
            logger.debug(f"Skipped file {path} ({reason})")
            return False

        try:
            # Extract text content from the file
            text = _extract(path)

            if not text or not text.strip():
                logger.info(f"Skipped file {path} (empty content after extraction)")
                _stats.skipped_no_content += 1
                return False

            # Normalize text: lowercase and strip extra whitespace
            text = text.strip()

            # Chunk the text into smaller pieces
            chunks = chunk_text(text)

            if not chunks:
                logger.debug(f"No chunks created from {path}, skipping")
                _stats.skipped_no_content += 1
                return False

            # Generate embeddings for all chunks
            vectors = self.embedder.embed_texts(chunks)

            # Filter out chunks where embedding failed (vector is None)
            valid_chunks = []
            valid_vectors = []
            meta_list = []

            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                if vector is not None:
                    valid_chunks.append(chunk)
                    valid_vectors.append(vector)
                    meta_list.append(
                        {
                            "path": str(path),
                            "chunk_idx": i,
                            "text": chunk,
                        }
                    )

            # Add valid vectors to FAISS index
            if valid_vectors:
                self.faiss.add(valid_vectors, meta_list)

            # Add valid chunks to BM25 index
            if valid_chunks:
                self.bm25.add(valid_chunks, meta_list)

            # Compute file hash for duplicate detection
            file_hash = _compute_file_hash(path)

            # Store file metadata in SQLite
            self.meta.upsert(
                path,
                chunk_count=len(valid_chunks),
                file_hash=file_hash,
            )

            logger.info(f"Indexed {path.name}: {len(valid_chunks)} chunks")

            return True

        except Exception as e:
            _stats.errors += 1
            logger.error(f"Failed to index {path}: {e}")
            return False

    def remove_file(self, path: Path) -> None:
        """
        Remove a file from all indexes.

        Args:
            path: Path to the file to remove
        """
        try:
            self.faiss.remove_by_path(str(path))
            self.bm25.remove_by_path(str(path))
            self.meta.delete(path)
            logger.info(f"Removed {path.name} from indexes")
        except Exception as e:
            logger.error(f"Failed to remove {path}: {e}")

    def reindex_file(self, path: Path) -> bool:
        """
        Reindex a file (remove and index again).

        Args:
            path: Path to the file to reindex

        Returns:
            True if file was reindexed successfully
        """
        self.remove_file(path)
        return self.index_file(path)
