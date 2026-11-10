"""Deterministic mock embedding provider for tests and local development (P2-02)."""

import hashlib
import math
import struct
from collections.abc import Sequence

from app.ai.providers.base import EmbeddingProvider
from app.ai.redaction import redact_secrets


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic, zero-network embedding provider for tests and offline usage."""

    def __init__(
        self,
        dimension: int = 1536,
        model_name: str = "fake-embedding-v1",
        custom_embeddings: dict[str, list[float]] | None = None,
    ) -> None:
        self._dimension = dimension
        self._model_name = model_name
        self._custom_embeddings = custom_embeddings or {}
        self.embedded_documents: list[list[str]] = []
        self.embedded_queries: list[str] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_deterministic_vector(self, text: str) -> list[float]:
        """Generate a reproducible, unit-normalized float vector based on text content.

        Combines full-text hash with token feature hashing so texts sharing terms
        have positive semantic similarity in tests and retrieval evaluation.
        """
        if text in self._custom_embeddings:
            custom_vec = self._custom_embeddings[text]
            if len(custom_vec) != self._dimension:
                raise ValueError(
                    f"Custom embedding dimension mismatch: expected {self._dimension}, got {len(custom_vec)}"
                )
            return custom_vec

        vec = [0.0] * self._dimension

        # 1. Base component from full-text SHA-256
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        for idx in range(self._dimension):
            h = int.from_bytes(hashlib.sha256(seed + struct.pack(">I", idx)).digest()[:4], "big")
            val = ((h / 0xFFFFFFFF) - 0.5) * 0.1
            vec[idx] += val

        # 2. Token feature hashing (bag-of-words projection)
        import re

        raw_tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        tokens: list[str] = []
        for t in raw_tokens:
            tokens.append(t)
            if "_" in t:
                tokens.extend(part for part in t.split("_") if part)

        for token in tokens:
            th = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:8], "big")
            bucket = th % self._dimension
            vec[bucket] += 1.0

        # 3. L2-normalize vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            return [x / norm for x in vec]
        return [1.0 / math.sqrt(self._dimension)] * self._dimension

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        redacted_texts = [redact_secrets(t) for t in texts]
        self.embedded_documents.append(list(redacted_texts))
        return [self._generate_deterministic_vector(t) for t in redacted_texts]

    async def embed_query(self, text: str) -> list[float]:
        redacted_text = redact_secrets(text)
        self.embedded_queries.append(redacted_text)
        return self._generate_deterministic_vector(redacted_text)
