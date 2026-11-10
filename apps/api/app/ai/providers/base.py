"""Base abstract interfaces for AI providers (P2-02, Hard Rule 7).

All LLM and embedding integrations must inherit from these interfaces and reside
strictly within `app.ai.providers`.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingProvider(ABC):
    """Abstract interface for generating vector embeddings."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the embedding model."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the generated embedding vectors."""
        ...

    @abstractmethod
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a sequence of documents/code chunks.

        Secrets are scrubbed before sending to external services.
        """
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single search query."""
        ...
