"""Centralized and configurable embedding manager for PRISM V4.

Supports customizable models, batch encoding, and filesystem caching.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path
import numpy as np

# Cache files
CACHE_FILE = Path(__file__).resolve().parents[1] / "scoring" / ".embeddings_cache.pkl"

class EmbeddingManager:
    """Centralized manager for SentenceTransformer models and embeddings caching."""

    _instance = None
    _model = None
    _cache = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str | None = None) -> None:
        # Resolve model name: constructor -> environment variable -> default
        self.model_name = model_name or os.environ.get("PRISM_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk if it exists."""
        if EmbeddingManager._cache is not None:
            return
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "rb") as f:
                    EmbeddingManager._cache = pickle.load(f)
            except Exception:
                EmbeddingManager._cache = {}
        else:
            EmbeddingManager._cache = {}

    def save_cache(self) -> None:
        """Save current cache to disk."""
        if EmbeddingManager._cache is None:
            return
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "wb") as f:
                pickle.dump(EmbeddingManager._cache, f)
        except Exception:
            pass

    def _get_model(self):
        """Lazily load SentenceTransformer model."""
        if EmbeddingManager._model is None:
            from sentence_transformers import SentenceTransformer
            # Disable tokenizers parallelism warning
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            EmbeddingManager._model = SentenceTransformer(self.model_name)
        return EmbeddingManager._model

    def _get_key(self, text: str) -> str:
        """Generate a deterministic key for a text string, including the model name to avoid conflicts."""
        raw_key = f"{self.model_name}:{text}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for a single text, encoding it lazily if not cached."""
        self._load_cache()
        key = self._get_key(text)
        if key not in EmbeddingManager._cache:
            model = self._get_model()
            embedding = model.encode(text, convert_to_numpy=True)
            EmbeddingManager._cache[key] = embedding
            self.save_cache()
        return EmbeddingManager._cache[key]

    def batch_encode(self, texts: list[str]) -> None:
        """Batch encode a list of texts and update the cache."""
        self._load_cache()
        unique_texts = list(set(texts))
        missing_texts = []
        for text in unique_texts:
            if not text or not text.strip():
                continue
            key = self._get_key(text)
            if key not in EmbeddingManager._cache:
                missing_texts.append(text)

        if missing_texts:
            model = self._get_model()
            embeddings = model.encode(missing_texts, convert_to_numpy=True)
            for text, emb in zip(missing_texts, embeddings):
                key = self._get_key(text)
                EmbeddingManager._cache[key] = emb
            self.save_cache()
