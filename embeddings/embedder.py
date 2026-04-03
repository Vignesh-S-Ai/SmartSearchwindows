# embeddings/embedder.py
# Handles embedding text using Gemini API with exponential backoff retry

import time
import math
from typing import Optional
from pathlib import Path

from config.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    EMBEDDING_DIM,
    EMBED_BATCH_SIZE,
    EMBED_MAX_RETRIES,
    EMBED_RETRY_DELAY,
)
from config.logger import get_logger
from cache.embedding_cache import EmbeddingCache

logger = get_logger(__name__)


class Embedder:
    """
    Handles text embedding generation using Gemini API.

    This class provides methods to embed text chunks into vector
    representations for semantic search. Uses exponential backoff
    retry for API calls and disk caching for embeddings.
    """

    def __init__(self, use_cache: bool = True) -> None:
        """
        Initialize the Embedder with API configuration.

        Args:
            use_cache: Whether to use embedding cache (default: True)
        """
        # Store the API key from configuration
        self.api_key = GEMINI_API_KEY
        # Store the model name to use for embeddings
        self.model = GEMINI_MODEL
        # Store the expected embedding dimension
        self.embedding_dim = EMBEDDING_DIM
        # Store batch size for processing multiple texts
        self.batch_size = EMBED_BATCH_SIZE
        # Store maximum retry attempts
        self.max_retries = EMBED_MAX_RETRIES
        # Store base delay between retries in seconds
        self.retry_delay = EMBED_RETRY_DELAY

        # Initialize embedding cache if enabled
        self.use_cache = use_cache
        self.cache = EmbeddingCache() if use_cache else None

        logger.info(
            f"Initialized Embedder with model: {self.model}, cache: {use_cache}"
        )

    def embed_texts(self, texts: list[str]) -> list[Optional[list[float]]]:
        """
        Embed a list of text strings into vector representations.

        This method takes a list of text chunks and returns corresponding
        embedding vectors. It handles batching, caching, and retries.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (one per input text), or None for failed embeddings
        """
        # Return list of None if no texts provided
        if not texts:
            return []

        # Initialize list to store embeddings
        embeddings = []

        # Process each text with caching
        for text in texts:
            # Try to get from cache first
            if self.cache:
                cached = self.cache.get(text)
                if cached is not None:
                    embeddings.append(cached)
                    continue

            # Compute embedding with retry
            embedding = self._embed_single_with_retry(text)

            # Store in cache if successful
            if embedding is not None and self.cache:
                self.cache.set(text, embedding)

            embeddings.append(embedding)

        return embeddings

    def _embed_single_with_retry(self, text: str) -> Optional[list[float]]:
        """
        Embed a single text with exponential backoff retry.

        Uses exponential backoff: delay = base_delay * 2^attempt
        Caps the delay at 60 seconds to avoid excessive waits.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                # Try to embed using Gemini API
                embedding = self._call_gemini_api(text)
                if embedding is not None:
                    return embedding

            except Exception as e:
                # Calculate exponential backoff delay
                # delay = base_delay * 2^attempt (with max cap)
                delay = min(
                    self.retry_delay * (2**attempt),
                    60.0,  # Maximum 60 second delay
                )

                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Embedding attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    # All retries failed
                    logger.error(
                        f"Failed to embed after {self.max_retries} attempts: {e}"
                    )

        return None

    def _call_gemini_api(self, text: str) -> Optional[list[float]]:
        """
        Call Gemini API to generate embedding.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        # Check if API key is available
        if not self.api_key:
            logger.warning("No GEMINI_API_KEY configured, using placeholder")
            return self._generate_placeholder_embeddings(1)[0]

        try:
            # Import google genai for API call
            import google.genai as genai

            # Configure the client
            client = genai.Client(api_key=self.api_key)

            # Call the embedding API
            result = client.models.embed_content(
                model=self.model,
                content=text,
            )

            # Extract embedding from response
            if result and hasattr(result, "embedding"):
                return result.embedding.values

            return None

        except ImportError:
            # google-genai not installed
            logger.warning("google-genai not installed, using placeholder")
            return self._generate_placeholder_embeddings(1)[0]
        except Exception as e:
            # Log any API errors
            logger.error(f"Gemini API call failed: {e}")
            raise  # Re-raise to trigger retry

    def _generate_placeholder_embeddings(
        self, count: int
    ) -> list[Optional[list[float]]]:
        """
        Generate placeholder embeddings for testing or when API unavailable.

        This is a temporary implementation that returns random vectors.
        Should only be used when Gemini API is not available.

        Args:
            count: Number of embeddings to generate

        Returns:
            List of random embedding vectors
        """
        import random

        # Generate random embeddings as placeholders
        # Each embedding is a list of random floats
        return [
            [random.random() for _ in range(self.embedding_dim)] for _ in range(count)
        ]

    def get_cache_stats(self) -> dict:
        """Get cache statistics if caching is enabled."""
        if self.cache:
            return self.cache.get_stats()
        return {}
