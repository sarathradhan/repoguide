"""Service for generating dense vector embeddings using SentenceTransformers."""
import logging
import threading
from typing import List, Optional
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger("repoguide.embeddings")

# Module-level singleton cache and thread lock
_model_lock = threading.Lock()
_cached_model: Optional[SentenceTransformer] = None


class EmbeddingService:
    """Manages the SentenceTransformer model lifecycle and embedding generation."""

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """
        Retrieve or lazily initialize the SentenceTransformer embedding model.
        Thread-safe singleton pattern avoids re-loading weights on each request.
        """
        global _cached_model
        if _cached_model is None:
            with _model_lock:
                if _cached_model is None:
                    model_name = settings.EMBEDDING_MODEL_NAME
                    logger.info("Loading embedding model '%s'...", model_name)
                    try:
                        _cached_model = SentenceTransformer(model_name)
                        logger.info("Embedding model '%s' loaded successfully.", model_name)
                    except Exception as exc:
                        logger.error("Failed to load embedding model '%s': %s", model_name, exc)
                        raise RuntimeError(f"Could not load embedding model: {str(exc)}") from exc
        return _cached_model

    @classmethod
    def embed_texts(cls, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate dense vector embeddings for a list of text chunks.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for model inference

        Returns:
            List of float embedding vectors (each of length 384 for all-MiniLM-L6-v2)
        """
        if not texts:
            return []

        model = cls.get_model()
        try:
            # normalize_embeddings=True ensures cosine similarity can be computed via dot product
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embeddings.tolist()
        except Exception as exc:
            logger.error("Error generating text embeddings: %s", exc)
            raise RuntimeError(f"Embedding generation failed: {str(exc)}") from exc

    @classmethod
    def embed_query(cls, query: str) -> List[float]:
        """
        Generate a dense vector embedding for a search query using the identical model and normalization.

        Args:
            query: User search query string

        Returns:
            Embedding vector as list of floats
        """
        query = query.strip()
        if not query:
            raise ValueError("Query string cannot be empty.")

        model = cls.get_model()
        try:
            embedding = model.encode(
                query,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embedding.tolist()
        except Exception as exc:
            logger.error("Error generating query embedding for '%s': %s", query, exc)
            raise RuntimeError(f"Query embedding generation failed: {str(exc)}") from exc

