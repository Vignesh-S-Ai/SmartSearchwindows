# indexer/bm25_index.py
# Phase 2: File Watcher & Crawler
# This module provides BM25 index for keyword search.

import pickle
from config.config import BM25_INDEX_PATH
from config.logger import get_logger

logger = get_logger(__name__)


class BM25Index:
    """
    BM25-based keyword index for text search.

    This class provides BM25 ranking for keyword matching,
    complementing the semantic FAISS search.
    """

    def __init__(self) -> None:
        """
        Initialize the BM25 index.

        Creates or loads the BM25 index.
        """
        # Store the path to the BM25 index file
        self.index_path = BM25_INDEX_PATH

        # Initialize empty index structures
        # vocabulary: maps terms to document frequencies
        self.vocabulary = {}
        # inverted_index: maps terms to (doc_id, term_freq) pairs
        self.inverted_index = {}
        # doc_lengths: stores length of each document
        self.doc_lengths = []
        # doc_ids: maps internal doc_id to path
        self.doc_ids = {}
        # Average document length for BM25 scoring
        self.avg_doc_length = 0

        # BM25 parameters
        self.k1 = 1.5  # Term frequency saturation parameter
        self.b = 0.75  # Length normalization parameter

        # Try to load existing index
        self._load_index()

        logger.info(f"Initialized BM25 index with {len(self.doc_ids)} documents")

    def _load_index(self) -> None:
        """Load existing BM25 index from disk if available."""
        if self.index_path.exists():
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                    self.vocabulary = data.get("vocabulary", {})
                    self.inverted_index = data.get("inverted_index", {})
                    self.doc_lengths = data.get("doc_lengths", [])
                    self.doc_ids = data.get("doc_ids", {})
                    self.avg_doc_length = data.get("avg_doc_length", 0)
            except Exception as e:
                logger.warning(f"Could not load BM25 index: {e}")

    def save(self) -> None:
        """Save the BM25 index to disk."""
        try:
            data = {
                "vocabulary": self.vocabulary,
                "inverted_index": self.inverted_index,
                "doc_lengths": self.doc_lengths,
                "doc_ids": self.doc_ids,
                "avg_doc_length": self.avg_doc_length,
            }
            with open(self.index_path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")

    def add(self, texts: list[str], metadata: list[dict]) -> None:
        """
        Add texts and their metadata to the BM25 index.

        Args:
            texts: List of text chunks to index
            metadata: List of metadata dicts corresponding to each text
        """
        if not texts:
            return

        try:
            # Get current doc_id (number of existing documents)
            doc_id = len(self.doc_lengths)

            # Process each text
            for i, (text, meta) in enumerate(zip(texts, metadata)):
                # Tokenize the text (simple whitespace tokenization)
                # In production, use proper tokenization (nltk, spacy, etc.)
                tokens = text.lower().split()

                # Store document length
                self.doc_lengths.append(len(tokens))

                # Store path mapping
                path = meta.get("path", f"doc_{doc_id}")
                self.doc_ids[doc_id] = path

                # Build inverted index
                term_freq = {}
                for token in tokens:
                    # Count term frequency in this document
                    term_freq[token] = term_freq.get(token, 0) + 1

                    # Update vocabulary with document frequency
                    if token not in self.vocabulary:
                        self.vocabulary[token] = 0
                    # We'll update DF after processing all docs

                # Add to inverted index
                for token, tf in term_freq.items():
                    if token not in self.inverted_index:
                        self.inverted_index[token] = []
                    self.inverted_index[token].append((doc_id, tf))

                # Update document frequency for each term
                for token in set(tokens):
                    self.vocabulary[token] = self.vocabulary.get(token, 0) + 1

                # Increment doc_id for next document
                doc_id += 1

            # Update average document length
            if self.doc_lengths:
                self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)

            # Save the index
            self.save()

        except Exception as e:
            logger.error(f"Failed to add to BM25 index: {e}")

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """
        Search for documents matching the query.

        Args:
            query: The search query string
            top_k: Number of results to return

        Returns:
            List of (path, score) tuples
        """
        if not query or not self.doc_lengths:
            return []

        try:
            # Tokenize query
            query_tokens = query.lower().split()

            # Calculate BM25 scores for each document
            doc_scores = {}
            num_docs = len(self.doc_lengths)

            for token in query_tokens:
                if token not in self.inverted_index:
                    continue

                # Get document frequency for this term
                df = self.vocabulary.get(token, 0)
                if df == 0:
                    continue

                # IDF calculation (standard BM25 formula)
                idf = max(0, (num_docs - df + 0.5) / (df + 0.5))
                idf = 1 + idf  # Smoothed IDF

                # Score each document containing this term
                for doc_id, tf in self.inverted_index[token]:
                    doc_len = self.doc_lengths[doc_id]

                    # BM25 scoring formula
                    score = (
                        idf
                        * (tf * (self.k1 + 1))
                        / (
                            tf
                            + self.k1
                            * (1 - self.b + self.b * doc_len / self.avg_doc_length)
                        )
                    )

                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + score

            # Sort by score and return top_k results
            sorted_docs = sorted(doc_scores.items(), key=lambda x: -x[1])
            results = []
            for doc_id, score in sorted_docs[:top_k]:
                path = self.doc_ids.get(doc_id, "")
                if path:
                    results.append((path, score))

            return results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def remove_by_path(self, path: str) -> None:
        """
        Remove all entries associated with a file path.

        Note: This is a simplified implementation. In production,
        you'd want to rebuild the index properly after removal.

        Args:
            path: The file path to remove
        """
        # Find doc_ids associated with this path
        doc_ids_to_remove = [doc_id for doc_id, p in self.doc_ids.items() if p == path]

        if doc_ids_to_remove:
            # Remove from doc_ids mapping
            for doc_id in doc_ids_to_remove:
                del self.doc_ids[doc_id]

            # Note: Full index rebuild would be needed to clean inverted_index
            # For now, just save the updated doc_ids
            self.save()
            logger.info(f"Removed BM25 entries for {path}")
