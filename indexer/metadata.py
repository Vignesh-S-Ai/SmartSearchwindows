# indexer/metadata.py
# Phase 2: File Watcher & Crawler
# This module provides SQLite database for file metadata storage.

import sqlite3
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from config.config import SQLITE_PATH, SQLITE_TIMEOUT
from config.logger import get_logger

logger = get_logger(__name__)


class MetadataStore:
    """
    SQLite-based metadata store for file information.

    This class manages file metadata including path, size,
    modification time, and indexed chunk count.
    """

    def __init__(self) -> None:
        """
        Initialize the metadata store.

        Creates or opens the SQLite database and initializes tables.
        """
        # Store the path to the SQLite database file
        self.db_path = SQLITE_PATH

        # Initialize the database
        self._init_db()

        logger.info(f"Initialized metadata store at {self.db_path}")

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        try:
            # Connect to SQLite database with timeout
            conn = sqlite3.connect(str(self.db_path), timeout=SQLITE_TIMEOUT)
            cursor = conn.cursor()

            # Create files table for storing file metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    size INTEGER,
                    modified_time REAL,
                    indexed_time REAL,
                    chunk_count INTEGER
                )
            """)

            # Create index on modified_time for recency sorting
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_modified_time 
                ON files(modified_time DESC)
            """)

            # Commit and close
            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def connect(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(str(self.db_path), timeout=SQLITE_TIMEOUT)

    def upsert(
        self, path: Path, chunk_count: int = 0, size: Optional[int] = None
    ) -> None:
        """
        Insert or update file metadata.

        Args:
            path: Path to the file
            chunk_count: Number of chunks indexed for this file
            size: File size in bytes (optional, will fetch if not provided)
        """
        try:
            # Get file size if not provided
            if size is None:
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0

            # Get modification time
            try:
                modified_time = path.stat().st_mtime
            except OSError:
                modified_time = 0

            # Get current time for indexing timestamp
            indexed_time = datetime.now().timestamp()

            # Connect and upsert
            conn = self.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO files 
                (path, size, modified_time, indexed_time, chunk_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(path), size, modified_time, indexed_time, chunk_count),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            logger.error(f"Failed to upsert metadata for {path}: {e}")

    def is_indexed(self, path: Path) -> bool:
        """
        Check if a file is already indexed and hasn't changed.

        Args:
            path: Path to the file

        Returns:
            True if file is indexed and unchanged, False otherwise
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            # Get stored metadata for this path
            cursor.execute(
                "SELECT size, modified_time FROM files WHERE path = ?",
                (str(path),),
            )
            row = cursor.fetchone()

            conn.close()

            if row is None:
                return False

            # Compare with current file stats
            try:
                current_size = path.stat().st_size
                current_mtime = path.stat().st_mtime

                # File is indexed if size and mtime match
                return row[0] == current_size and row[1] == current_mtime

            except OSError:
                # File doesn't exist anymore
                return False

        except sqlite3.Error as e:
            logger.error(f"Failed to check indexed status for {path}: {e}")
            return False

    def delete(self, path: Path) -> None:
        """
        Delete file metadata.

        Args:
            path: Path to the file
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM files WHERE path = ?", (str(path),))

            conn.commit()
            conn.close()

            logger.info(f"Deleted metadata for {path}")

        except sqlite3.Error as e:
            logger.error(f"Failed to delete metadata for {path}: {e}")

    def get_chunk_count(self, path: Path) -> int:
        """
        Get the number of chunks indexed for a file.

        Args:
            path: Path to the file

        Returns:
            Number of chunks, or 0 if not found
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT chunk_count FROM files WHERE path = ?",
                (str(path),),
            )
            row = cursor.fetchone()

            conn.close()

            return row[0] if row else 0

        except sqlite3.Error as e:
            logger.error(f"Failed to get chunk count for {path}: {e}")
            return 0

    def get_all_paths(self) -> list[str]:
        """
        Get all indexed file paths.

        Returns:
            List of file paths
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            cursor.execute("SELECT path FROM files")
            rows = cursor.fetchall()

            conn.close()

            return [row[0] for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Failed to get all paths: {e}")
            return []
