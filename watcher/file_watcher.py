# watcher/file_watcher.py
# Phase 2: File Watcher & Crawler
# This module provides file system watching using watchdog.

import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config.config import WATCH_PATHS, SUPPORTED_EXTENSIONS, IGNORE_DIRS
from config.logger import get_logger

logger = get_logger(__name__)


class _SearchEventHandler(FileSystemEventHandler):
    """
    Private event handler for file system events.

    This class handles file creation, modification, deletion, and move events,
    filtering based on supported file extensions and ignored directories.
    """

    def __init__(
        self,
        on_create: Callable[[Path], None],
        on_modify: Callable[[Path], None],
        on_delete: Callable[[Path], None],
    ) -> None:
        """
        Initialize the event handler with callback functions.

        Args:
            on_create: Callback function for file creation events
            on_modify: Callback function for file modification events
            on_delete: Callback function for file deletion events
        """
        # Store the callback functions for each event type
        self.on_create = on_create
        self.on_modify = on_modify
        self.on_delete = on_delete

    @staticmethod
    def _accept(path_str: str) -> bool:
        """
        Check if a file should be accepted for indexing.

        This method returns True only if:
        - The file extension is in SUPPORTED_EXTENSIONS
        - No part of the path is in IGNORE_DIRS

        Args:
            path_str: The file path as a string

        Returns:
            True if the file should be indexed, False otherwise
        """
        # Convert string path to Path object for easier manipulation
        path = Path(path_str)

        # Check if extension is supported
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False

        # Check if any part of the path is in ignore directories
        # Convert path parts to strings for comparison
        path_parts = [part.lower() for part in path.parts]
        for ignore_dir in IGNORE_DIRS:
            if ignore_dir.lower() in path_parts:
                return False

        # All checks passed - file should be indexed
        return True

    def on_created(self, event) -> None:
        """
        Handle file creation events.

        Called when a file or directory is created. Only processes files.

        Args:
            event: The watchdog event object
        """
        # Skip directory events - we only care about files
        if event.is_directory:
            return

        # Check if the file passes our acceptance criteria
        if self._accept(event.src_path):
            # Call the on_create callback with the file path
            self.on_create(Path(event.src_path))
            logger.debug(f"File created: {event.src_path}")

    def on_modified(self, event) -> None:
        """
        Handle file modification events.

        Called when a file is modified. Only processes files.

        Args:
            event: The watchdog event object
        """
        # Skip directory events - we only care about files
        if event.is_directory:
            return

        # Check if the file passes our acceptance criteria
        if self._accept(event.src_path):
            # Call the on_modify callback with the file path
            self.on_modify(Path(event.src_path))
            logger.debug(f"File modified: {event.src_path}")

    def on_deleted(self, event) -> None:
        """
        Handle file deletion events.

        Called when a file or directory is deleted.

        Args:
            event: The watchdog event object
        """
        # Skip directory events - we only care about files
        if event.is_directory:
            return

        # Call the on_delete callback - no extension check needed
        # The file is already gone, but we still need to clean up the index
        self.on_delete(Path(event.src_path))
        logger.debug(f"File deleted: {event.src_path}")

    def on_moved(self, event) -> None:
        """
        Handle file move/rename events.

        Called when a file is moved or renamed. Treats this as a delete
        of the old path followed by a create of the new path.

        Args:
            event: The watchdog event object containing src_path and dest_path
        """
        # Handle the old path (file was moved away)
        self.on_delete(Path(event.src_path))
        logger.debug(f"File moved from: {event.src_path}")

        # Handle the new path (file was moved to)
        # Only index if the new path passes acceptance criteria
        if self._accept(event.dest_path):
            self.on_create(Path(event.dest_path))
            logger.debug(f"File moved to: {event.dest_path}")


class FileWatcher:
    """
    Public class for watching file system changes.

    This class monitors specified directories for file changes and
    triggers appropriate callbacks for create, modify, and delete events.
    """

    def __init__(
        self,
        on_create: Callable[[Path], None],
        on_modify: Callable[[Path], None],
        on_delete: Callable[[Path], None],
        watch_paths: Optional[list[Path]] = None,
    ) -> None:
        """
        Initialize the file watcher.

        Args:
            on_create: Callback for file creation events
            on_modify: Callback for file modification events
            on_delete: Callback for file deletion events
            watch_paths: List of paths to watch (defaults to WATCH_PATHS config)
        """
        # Create the watchdog observer
        self.observer = Observer()

        # Create the event handler with our callbacks
        self.handler = _SearchEventHandler(on_create, on_modify, on_delete)

        # Use provided paths or fall back to config WATCH_PATHS
        if watch_paths is not None:
            self.watch_paths = watch_paths
        else:
            self.watch_paths = WATCH_PATHS

        logger.info(f"FileWatcher initialized with paths: {self.watch_paths}")

    def start(self) -> None:
        """
        Start watching the configured directories.

        Schedules each path to be watched recursively and starts the observer.
        Logs each path that is being watched.
        """
        # Loop through each path to watch
        for path in self.watch_paths:
            # Skip paths that don't exist
            if not path.exists():
                logger.warning(f"Watch path does not exist: {path}")
                continue

            # Skip paths that aren't directories
            if not path.is_dir():
                logger.warning(f"Watch path is not a directory: {path}")
                continue

            # Schedule this path for watching with recursive=True
            # This watches the directory and all its subdirectories
            self.observer.schedule(self.handler, str(path), recursive=True)
            logger.info(f"Now watching: {path}")

        # Start the observer - this runs in a background thread
        self.observer.start()
        logger.info("File watcher started")

    def stop(self) -> None:
        """
        Stop watching for file changes.

        Stops the observer and waits for it to finish cleanly.
        """
        # Stop the observer
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

        logger.info("File watcher stopped")

    def run_forever(self) -> None:
        """
        Start the watcher and run until interrupted.

        This is a convenience method that starts the watcher and then
        loops indefinitely until a KeyboardInterrupt is received.
        """
        # Start watching
        self.start()

        try:
            # Loop forever, sleeping for 1 second between iterations
            # This keeps the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # User pressed Ctrl+C - gracefully shut down
            logger.info("KeyboardInterrupt received, stopping watcher...")
            self.stop()
