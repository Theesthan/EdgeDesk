"""Local FAISS vector store for semantic rule search.

Uses sentence-transformers (all-MiniLM-L6-v2) for embeddings.
Auto-persists to disk every 10 inserts.
No internet required after initial model download.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import faiss
import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer

_EMBED_MODEL = "all-MiniLM-L6-v2"
_PERSIST_INTERVAL = 10
_DIM = 384  # all-MiniLM-L6-v2 output dimension


class VectorStore:
    """FAISS-backed semantic search over rule descriptions."""

    def __init__(self, data_dir: Path | None = None) -> None:
        raw = os.environ.get("DATA_DIR", "~/.edgedesk")
        self._data_dir = data_dir or Path(raw).expanduser().resolve()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._index_path = self._data_dir / "rules.faiss"
        self._ids_path = self._data_dir / "rules_ids.json"

        self._model: SentenceTransformer | None = None
        self._index: faiss.IndexFlatL2 | None = None
        self._rule_ids: list[str] = []
        self._insert_count = 0

        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_rule(self, rule_id: str, text: str) -> None:
        """Encode *text* and add to the index with *rule_id* as key."""
        vec = self._encode(text)
        self._get_index().add(np.array([vec], dtype=np.float32))
        self._rule_ids.append(rule_id)
        self._insert_count += 1
        if self._insert_count % _PERSIST_INTERVAL == 0:
            self.persist()
            logger.debug("VectorStore auto-persisted after {} inserts.", self._insert_count)

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Return up to *k* (rule_id, distance) pairs for *query*."""
        if self._index is None or self._index.ntotal == 0:
            return []
        k = min(k, self._index.ntotal)
        vec = self._encode(query)
        distances, indices = self._get_index().search(
            np.array([vec], dtype=np.float32), k
        )
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self._rule_ids):
                results.append((self._rule_ids[idx], float(dist)))
        return results

    def persist(self) -> None:
        """Write index and rule-id map to disk."""
        if self._index is not None:
            faiss.write_index(self._index, str(self._index_path))
            self._ids_path.write_text(json.dumps(self._rule_ids), encoding="utf-8")
            logger.debug("VectorStore persisted ({} vectors).", self._index.ntotal)

    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule from the in-memory id list (index rebuild required)."""
        if rule_id in self._rule_ids:
            self._rule_ids.remove(rule_id)

    @property
    def size(self) -> int:
        """Number of vectors in the index."""
        return self._index.ntotal if self._index else 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading sentence-transformers model: {}", _EMBED_MODEL)
            self._model = SentenceTransformer(_EMBED_MODEL)
        return self._model

    def _get_index(self) -> faiss.IndexFlatL2:
        if self._index is None:
            self._index = faiss.IndexFlatL2(_DIM)
        return self._index

    def _encode(self, text: str) -> np.ndarray:
        embedding = self._get_model().encode(text, convert_to_numpy=True)
        return embedding.astype(np.float32)

    def _load(self) -> None:
        """Load persisted index from disk if available."""
        if self._index_path.exists() and self._ids_path.exists():
            try:
                self._index = faiss.read_index(str(self._index_path))
                self._rule_ids = json.loads(self._ids_path.read_text(encoding="utf-8"))
                logger.info(
                    "VectorStore loaded from disk ({} vectors).", self._index.ntotal
                )
            except Exception as exc:
                logger.warning("Failed to load VectorStore from disk: {}. Starting fresh.", exc)
                self._index = None
                self._rule_ids = []
