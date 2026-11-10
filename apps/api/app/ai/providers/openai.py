"""OpenAI Embedding Provider implementation (P2-02, ADR 11).

Calls OpenAI's REST API using httpx with automatic secret scrubbing and batching.
"""

import logging
from collections.abc import Sequence
from typing import Any

import httpx

from app.ai.providers.base import EmbeddingProvider
from app.ai.redaction import redact_secrets

logger = logging.getLogger("repopilot.ai.providers.openai")


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Generates vector embeddings using OpenAI's REST API (e.g. text-embedding-3-small)."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "text-embedding-3-small",
        dimension: int = 1536,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        batch_size: int = 100,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key must not be empty.")
        self._api_key = api_key
        self._model_name = model_name
        self._dimension = dimension
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._batch_size = max(1, batch_size)
        self._client = client

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _post_embeddings(
        self, client: httpx.AsyncClient, texts: list[str]
    ) -> list[list[float]]:
        """Send a single batch of texts to the embeddings endpoint."""
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model_name,
            "input": texts,
            "dimensions": self._dimension,
        }

        response = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=self._timeout_seconds,
        )

        if response.status_code != 200:
            error_msg = f"OpenAI Embedding API error {response.status_code}: {response.text}"
            logger.error(error_msg)
            response.raise_for_status()

        data = response.json()
        items = data.get("data", [])
        # Ensure ordering by index
        items.sort(key=lambda x: int(x.get("index", 0)))
        return [list(item["embedding"]) for item in items]

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a list of code chunks or document texts in batches with secret scrubbing."""
        if not texts:
            return []

        # Scrub all secrets prior to transmission (Hard Rule 4)
        scrubbed = [redact_secrets(t) for t in texts]
        results: list[list[float]] = []

        if self._client is not None:
            for i in range(0, len(scrubbed), self._batch_size):
                batch = scrubbed[i : i + self._batch_size]
                batch_embeddings = await self._post_embeddings(self._client, batch)
                results.extend(batch_embeddings)
        else:
            async with httpx.AsyncClient() as client:
                for i in range(0, len(scrubbed), self._batch_size):
                    batch = scrubbed[i : i + self._batch_size]
                    batch_embeddings = await self._post_embeddings(client, batch)
                    results.extend(batch_embeddings)

        return results

    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query with secret scrubbing."""
        embeddings = await self.embed_documents([text])
        if not embeddings:
            raise RuntimeError("Received empty embedding from OpenAI API.")
        return embeddings[0]
