"""Tests for EmbeddingProvider interface, OpenAI implementation, Fake provider, and secret redaction (P2-02).

Enforces:
- Hard Rule 4: Never log or send secrets/tokens. Redact before any LLM call.
- Hard Rule 7: LLM/embedding calls go ONLY through apps/api/app/ai/providers/.
"""

import math

import httpx
import pytest

from app.ai.providers import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from app.ai.redaction import redact_secrets
from app.core.config import Settings


def test_redact_secrets_masks_sensitive_tokens() -> None:
    """Verifies that secrets and API keys are scrubbed before sending over the wire."""
    raw_text = (
        "Here is an AWS key AKIAIOSFODNN7EXAMPLE and github token ghp_abcdefghijklmnopqrstuvwxyz0123456789. "
        "Also sk-proj-1234567890abcdefghijklmnopqrstuvwxyz1234567890 and slack token xoxb-1234567890-1234567890123. "
        'const api_key = "secret_value_1234567890_abcdef";'
    )
    scrubbed = redact_secrets(raw_text)

    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "[REDACTED_AWS_KEY]" in scrubbed
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in scrubbed
    assert "[REDACTED_GITHUB_TOKEN]" in scrubbed
    assert "[REDACTED_OPENAI_KEY]" in scrubbed
    assert "[REDACTED_SLACK_TOKEN]" in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed


@pytest.mark.asyncio
async def test_fake_embedding_provider_deterministic_and_normalized() -> None:
    """FakeEmbeddingProvider outputs reproducible, normalized vectors of correct dimension."""
    provider = FakeEmbeddingProvider(dimension=64, model_name="fake-v1")
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension == 64
    assert provider.model_name == "fake-v1"

    text = "def calculate_risk(metric: float) -> float:\n    return metric * 2.0"
    v1 = await provider.embed_query(text)
    v2 = await provider.embed_query(text)

    # Determinism: same input -> identical embedding
    assert len(v1) == 64
    assert v1 == v2

    # L2 unit normalization: sqrt(sum(x^2)) ≈ 1.0
    norm = math.sqrt(sum(x * x for x in v1))
    assert abs(norm - 1.0) < 1e-5

    # Distinct texts yield distinct embeddings
    v_other = await provider.embed_query("completely different input text")
    assert v1 != v_other

    # Query log tracked
    assert len(provider.embedded_queries) == 3


@pytest.mark.asyncio
async def test_fake_embedding_provider_embed_documents() -> None:
    """FakeEmbeddingProvider embeds batches of documents and scrubs secrets."""
    provider = FakeEmbeddingProvider(dimension=16)
    docs = [
        "doc1: normal text",
        "doc2: secret AKIA1111111111111111 inside text",
    ]
    vectors = await provider.embed_documents(docs)

    assert len(vectors) == 2
    assert len(vectors[0]) == 16
    assert len(vectors[1]) == 16
    # Verify recorded documents had secrets scrubbed
    assert "[REDACTED_AWS_KEY]" in provider.embedded_documents[0][1]
    assert "AKIA1111111111111111" not in provider.embedded_documents[0][1]


@pytest.mark.asyncio
async def test_fake_embedding_provider_custom_mapping() -> None:
    """Custom predefined vectors can be injected for specific test scenarios."""
    custom = {"alpha": [1.0, 0.0], "beta": [0.0, 1.0]}
    provider = FakeEmbeddingProvider(dimension=2, custom_embeddings=custom)
    vec = await provider.embed_query("alpha")
    assert vec == [1.0, 0.0]


def test_openai_provider_rejects_empty_key() -> None:
    """OpenAIEmbeddingProvider requires a valid API key string."""
    with pytest.raises(ValueError, match="OpenAI API key must not be empty"):
        OpenAIEmbeddingProvider(api_key="")


@pytest.mark.asyncio
async def test_openai_embedding_provider_mock_transport() -> None:
    """OpenAIEmbeddingProvider makes properly structured REST requests and parses responses."""
    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        data = {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "index": 0,
                    "embedding": [0.1, 0.2, 0.3],
                },
                {
                    "object": "embedding",
                    "index": 1,
                    "embedding": [0.4, 0.5, 0.6],
                },
            ],
            "model": "text-embedding-3-small",
            "usage": {"prompt_tokens": 12, "total_tokens": 12},
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIEmbeddingProvider(
            api_key="test-key-12345",
            model_name="text-embedding-3-small",
            dimension=3,
            client=client,
        )

        texts = [
            "function one with AWS AKIAIOSFODNN7EXAMPLE",
            "function two standard",
        ]
        embeddings = await provider.embed_documents(texts)

        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]

        # Verify wire request
        assert len(captured_requests) == 1
        req = captured_requests[0]
        assert req.url == "https://api.openai.com/v1/embeddings"
        assert req.headers["Authorization"] == "Bearer test-key-12345"

        import json

        body = json.loads(req.content.decode("utf-8"))
        assert body["model"] == "text-embedding-3-small"
        assert body["dimensions"] == 3
        # Hard Rule 4: Secret was scrubbed before network transmission
        assert "AKIAIOSFODNN7EXAMPLE" not in body["input"][0]
        assert "[REDACTED_AWS_KEY]" in body["input"][0]


@pytest.mark.asyncio
async def test_openai_embedding_provider_error_handling() -> None:
    """OpenAIEmbeddingProvider raises exception when API returns non-200 status."""

    def mock_error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    transport = httpx.MockTransport(mock_error_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIEmbeddingProvider(
            api_key="invalid-key",
            client=client,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await provider.embed_query("test query")


def test_get_embedding_provider_factory() -> None:
    """Factory resolves providers correctly based on configuration."""
    settings = Settings(
        EMBEDDING_PROVIDER="fake",
        EMBEDDING_DIMENSION=128,
        EMBEDDING_MODEL="test-model",
    )
    provider = get_embedding_provider(settings=settings)
    assert isinstance(provider, FakeEmbeddingProvider)
    assert provider.dimension == 128
    assert provider.model_name == "test-model"

    # OpenAI without API key raises ValueError
    settings_no_key = Settings(EMBEDDING_PROVIDER="openai", OPENAI_API_KEY=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is required"):
        get_embedding_provider(settings=settings_no_key)

    # OpenAI with key succeeds
    settings_with_key = Settings(
        EMBEDDING_PROVIDER="openai",
        OPENAI_API_KEY="sk-test-valid-key",
        EMBEDDING_DIMENSION=1536,
    )
    openai_provider = get_embedding_provider(settings=settings_with_key)
    assert isinstance(openai_provider, OpenAIEmbeddingProvider)
    assert openai_provider.dimension == 1536

    # Unsupported provider raises ValueError
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        get_embedding_provider("cohere", settings=settings)
