# search/query_engine.py
# Hybrid search engine combining semantic (FAISS), keyword (BM25), and fuzzy matching

import math
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from config.config import ALPHA, RECENCY_BOOST, TOP_K
from config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Data class for search results with scoring information."""

    path: str
    chunk_idx: int
    text: str
    semantic_score: float
    keyword_score: float
    fuzzy_score: float
    recency_score: float
    final_score: float
    file_name: str


class QueryEngine:
    """
    Hybrid search engine combining FAISS semantic search,
    BM25 keyword search, and fuzzy matching.
    """

    def __init__(
        self,
        faiss,
        bm25,
        metadata,
        embedder,
    ) -> None:
        """
        Initialize the query engine with search components.

        Args:
            faiss: FAISSIndex instance for semantic search
            bm25: BM25Index instance for keyword search
            metadata: MetadataStore instance for file metadata
            embedder: Embedder instance for query embedding
        """
        # Store all search components
        self.faiss = faiss
        self.bm25 = bm25
        self.metadata = metadata
        self.embedder = embedder

        # Search configuration from config
        self.alpha = ALPHA  # Weight for semantic vs keyword (0.6 = 60% semantic)
        self.recency_boost = RECENCY_BOOST  # Boost for recent files
        self.top_k = TOP_K  # Number of results to return

        # Import rapidfuzz for fuzzy matching
        try:
            from rapidfuzz import fuzz, process

            self.fuzz = fuzz
            self.fuzz_process = process
        except ImportError:
            logger.warning("rapidfuzz not installed, fuzzy matching disabled")
            self.fuzz = None
            self.fuzz_process = None

        # Cache for normalizing scores between 0-1
        self._semantic_max = 1.0
        self._keyword_max = 1.0
        self._fuzzy_max = 1.0

        logger.info("QueryEngine initialized with hybrid search")

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        alpha: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        Perform hybrid search combining semantic, keyword, and fuzzy matching.

        Final score formula:
        final_score = alpha * normalized_semantic + (1-alpha) * normalized_keyword
                     + recency_boost + fuzzy_boost

        Args:
            query: The search query string
            top_k: Number of results to return (defaults to config TOP_K)
            alpha: Override for semantic/keyword weight

        Returns:
            List of SearchResult objects ranked by final_score
        """
        if not query or not query.strip():
            return []

        # Use provided values or fall back to config
        k = top_k if top_k is not None else self.top_k
        search_alpha = alpha if alpha is not None else self.alpha

        logger.info(f"Searching for: {query}")

        try:
            # Step 1: Get semantic search results from FAISS
            semantic_results = self._semantic_search(query, k * 2)

            # Step 2: Get keyword search results from BM25
            keyword_results = self._keyword_search(query, k * 2)

            # Step 3: Get fuzzy matching results
            fuzzy_results = self._fuzzy_search(query, k * 2)

            # Step 4: Combine and score all results
            combined = self._combine_results(
                semantic_results,
                keyword_results,
                fuzzy_results,
                search_alpha,
            )

            # Step 5: Apply recency boost
            combined = self._apply_recency_boost(combined)

            # Step 6: Sort by final score and return top k
            combined.sort(key=lambda x: x.final_score, reverse=True)
            results = combined[:k]

            logger.info(f"Found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _semantic_search(self, query: str, k: int) -> dict[str, tuple[str, float]]:
        """
        Perform semantic search using FAISS.

        Args:
            query: Search query
            k: Number of results to fetch

        Returns:
            Dict mapping path -> (text, score)
        """
        results = {}

        try:
            # Embed the query text
            query_vectors = self.embedder.embed_texts([query])

            if not query_vectors or query_vectors[0] is None:
                logger.warning("Failed to embed query")
                return results

            query_vector = query_vectors[0]

            # Search FAISS index
            faiss_results = self.faiss.search(query_vector, k)

            # Process results
            for meta, distance in faiss_results:
                path = meta.get("path", "")
                if path:
                    # Convert distance to similarity score (lower distance = higher similarity)
                    # Use exponential decay for better scoring
                    score = math.exp(-distance / 10.0)
                    results[path] = (meta.get("text", ""), score)

            # Update max for normalization
            if results:
                self._semantic_max = max(r[1] for r in results.values())

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")

        return results

    def _keyword_search(self, query: str, k: int) -> dict[str, tuple[str, float]]:
        """
        Perform keyword search using BM25.

        Args:
            query: Search query
            k: Number of results to fetch

        Returns:
            Dict mapping path -> (text, score)
        """
        results = {}

        try:
            # Search BM25 index
            bm25_results = self.bm25.search(query, k)

            # Process results
            for path, score in bm25_results:
                # Get text from metadata if available
                text = self._get_text_for_path(path)
                results[path] = (text, score)

            # Update max for normalization
            if results:
                self._keyword_max = max(r[1] for r in results.values())

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")

        return results

    def _fuzzy_search(self, query: str, k: int) -> dict[str, tuple[str, float]]:
        """
        Perform fuzzy matching using rapidfuzz.

        Args:
            query: Search query
            k: Number of results to fetch

        Returns:
            Dict mapping path -> (text, score)
        """
        if self.fuzz is None or self.fuzz_process is None:
            return {}

        results = {}

        try:
            # Get all indexed file paths
            all_paths = self.metadata.get_all_paths()

            if not all_paths:
                return results

            # Extract file names for fuzzy matching
            file_names = [Path(p).name for p in all_paths]

            # Use rapidfuzz process.extract for fuzzy matching
            # This finds similar strings even with typos
            fuzzy_matches = self.fuzz_process.extract(
                query,
                file_names,
                limit=k,
                score_cutoff=50,  # Minimum score to consider
            )

            # Process fuzzy matches
            for match in fuzzy_matches:
                idx = match[2]  # Index in original list
                path = all_paths[idx]
                score = match[1] / 100.0  # Convert to 0-1 scale

                text = self._get_text_for_path(path)
                results[path] = (text, score)

            # Update max for normalization
            if results:
                self._fuzzy_max = max(r[1] for r in results.values())

        except Exception as e:
            logger.error(f"Fuzzy search failed: {e}")

        return results

    def _get_text_for_path(self, path: str) -> str:
        """Get text content for a path from metadata."""
        # This would need to be implemented with a proper text store
        # For now, return empty string
        return ""

    def _combine_results(
        self,
        semantic: dict,
        keyword: dict,
        fuzzy: dict,
        alpha: float,
    ) -> list[SearchResult]:
        """
        Combine results from all search methods and calculate final scores.

        Args:
            semantic: Semantic search results
            keyword: Keyword search results
            fuzzy: Fuzzy search results
            alpha: Weight for semantic vs keyword

        Returns:
            List of SearchResult objects with combined scores
        """
        # Collect all unique paths
        all_paths = set(semantic.keys()) | set(keyword.keys()) | set(fuzzy.keys())

        results = []

        for path in all_paths:
            # Get text and scores from each source
            sem_text, sem_score = semantic.get(path, ("", 0.0))
            kw_text, kw_score = keyword.get(path, ("", 0.0))
            fuzzy_text, fuzzy_score = fuzzy.get(path, ("", 0.0))

            # Use the longest text available
            text = sem_text or kw_text or fuzzy_text or ""

            # Normalize scores to 0-1 range
            norm_sem = sem_score / self._semantic_max if self._semantic_max > 0 else 0
            norm_kw = kw_score / self._keyword_max if self._keyword_max > 0 else 0
            norm_fuzzy = fuzzy_score / self._fuzzy_max if self._fuzzy_max > 0 else 0

            # Calculate hybrid score
            # semantic_score * alpha + keyword_score * (1-alpha)
            combined_keyword = norm_sem * alpha + norm_kw * (1 - alpha)

            # Add fuzzy boost (small additional score for fuzzy matches)
            fuzzy_boost = norm_fuzzy * 0.1  # 10% weight for fuzzy

            # Create result object
            result = SearchResult(
                path=path,
                chunk_idx=0,
                text=text,
                semantic_score=norm_sem,
                keyword_score=norm_kw,
                fuzzy_score=norm_fuzzy,
                recency_score=0.0,  # Will be updated in recency boost
                final_score=combined_keyword + fuzzy_boost,
                file_name=Path(path).name,
            )

            results.append(result)

        return results

    def _apply_recency_boost(self, results: list[SearchResult]) -> list[SearchResult]:
        """
        Apply recency boost to search results.

        Files modified in the last 7 days get a boost.
        More recent files get higher boost.

        Args:
            results: List of SearchResult objects

        Returns:
            Results with recency boost applied
        """
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)

        for result in results:
            try:
                # Get file modification time from metadata
                path = Path(result.path)
                if not path.exists():
                    continue

                # Get modification time
                mtime = datetime.fromtimestamp(path.stat().st_mtime)

                # Check if file was modified in last 7 days
                if mtime > seven_days_ago:
                    # Calculate boost based on how recent
                    days_ago = (now - mtime).days
                    boost = self.recency_boost * (1 - days_ago / 7)
                    boost = max(0, boost)  # Ensure non-negative

                    result.recency_score = boost
                    result.final_score += boost

            except OSError:
                continue

        return results
