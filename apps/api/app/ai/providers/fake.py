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
        """Generate a reproducible, unit-normalized float vector based on text content."""
        if text in self._custom_embeddings:
            custom_vec = self._custom_embeddings[text]
            if len(custom_vec) != self._dimension:
                raise ValueError(
                    f"Custom embedding dimension mismatch: expected {self._dimension}, got {len(custom_vec)}"
                )
            return custom_vec

        # Use SHA-256 stream to generate deterministic pseudo-random values
        vec: list[float] = []
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        counter = 0

        while len(vec) < self._dimension:
            block = hashlib.sha256(seed + struct.pack(">I", counter)).digest()
            # Unpack into 8 floats (32 bytes = 8 x 4-byte standard floats)
            for k in range(0, 32, 4):
                if len(vec) >= self._dimension:
                    break
                val = struct.unpack(">f", block[k : k + 4])[0]
                # Replace inf/nan with 0.0 if any
                if math.isnan(val) or math.isinf(val):
                    val = 0.0
                vec.append(val)
            counter += 1

        # L2-normalize vector
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
