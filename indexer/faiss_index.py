# indexer/faiss_index.py
# Phase 2: File Watcher & Crawler
# This module provides FAISS vector index for semantic search.

import json
from config.config import FAISS_INDEX_PATH, FAISS_META_PATH, EMBEDDING_DIM
from config.logger import get_logger

logger = get_logger(__name__)


class FAISSIndex:
    """
    FAISS-based vector index for semantic search.

    This class wraps the FAISS library to provide efficient
    similarity search over embedded text chunks.
    """

    def __init__(self) -> None:
        """
        Initialize the FAISS index.

        Creates or loads the FAISS index and its metadata.
        """
        # Store the path to the FAISS index file
        self.index_path = FAISS_INDEX_PATH
        # Store the path to the metadata file
        self.meta_path = FAISS_META_PATH
        # Store the embedding dimension
        self.embedding_dim = EMBEDDING_DIM

        # Try to load existing index, otherwise create new one
        try:
            # Import faiss here to make it optional
            import faiss

            self.faiss = faiss
            self.index = self._load_index()
            self.metadata = self._load_metadata()
            logger.info(f"Loaded FAISS index with {self.get_count()} vectors")
        except ImportError:
            # FAISS not installed - create mock index for testing
            logger.warning("FAISS not available, using mock index")
            self.faiss = None
            self.index = None
            self.metadata = {}

    def _load_index(self):
        """Load existing FAISS index from disk, or return None if not found."""
        import faiss

        if self.index_path.exists():
            try:
                return faiss.read_index(str(self.index_path))
            except Exception as e:
                logger.warning(f"Could not load FAISS index: {e}")
        return None

    def _load_metadata(self) -> dict:
        """Load metadata from JSON file, or return empty dict if not found."""
        if self.meta_path.exists():
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load metadata: {e}")
        return {}

    def save(self) -> None:
        """Save the FAISS index and metadata to disk."""
        if self.index is not None:
            try:
                self.faiss.write_index(self.index, str(self.index_path))
            except Exception as e:
                logger.error(f"Failed to save FAISS index: {e}")

        try:
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def add(self, vectors: list, metadata: list[dict]) -> None:
        """
        Add vectors and their metadata to the index.

        Args:
            vectors: List of embedding vectors
            metadata: List of metadata dicts corresponding to each vector
        """
        if not vectors or self.faiss is None:
            return

        try:
            # Convert vectors to numpy array with float32 type
            import numpy as np

            arr = np.array(vectors, dtype=np.float32)

            # Create index if it doesn't exist
            if self.index is None:
                self.index = self.faiss.IndexFlatL2(self.embedding_dim)

            # Add vectors to index
            self.index.add(arr)

            # Store metadata - keyed by path to allow removal
            for meta in metadata:
                path = meta.get("path", "")
                if path not in self.metadata:
                    self.metadata[path] = []
                self.metadata[path].append(meta)

            # Save after adding
            self.save()

        except Exception as e:
            logger.error(f"Failed to add vectors to FAISS index: {e}")

    def search(
        self, query_vector: list[float], top_k: int = 20
    ) -> list[tuple[dict, float]]:
        """
        Search for similar vectors.

        Args:
            query_vector: The query embedding vector
            top_k: Number of results to return

        Returns:
            List of (metadata, distance) tuples
        """
        if self.index is None:
            return []

        try:
            import numpy as np

            # Convert query to numpy array
            query = np.array([query_vector], dtype=np.float32)

            # Search the index
            distances, indices = self.index.search(query, top_k)

            # Build results from metadata
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx >= 0:
                    # Find metadata for this index
                    for path, metas in self.metadata.items():
                        for meta in metas:
                            if meta.get("chunk_idx") == idx:
                                results.append((meta, float(dist)))
                                break

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def remove_by_path(self, path: str) -> None:
        """
        Remove all vectors associated with a file path.

        Args:
            path: The file path to remove
        """
        if path in self.metadata:
            del self.metadata[path]
            self.save()
            logger.info(f"Removed FAISS entries for {path}")

    def get_count(self) -> int:
        """Get the number of vectors in the index."""
        if self.index is not None:
            return self.index.ntotal
        return 0
