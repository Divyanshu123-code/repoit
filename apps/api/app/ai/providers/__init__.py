"""AI Provider interfaces and implementations (P2-02, Hard Rule 7).

All vendor and testing providers for LLM completions and embeddings reside here.
"""

from app.ai.providers.base import EmbeddingProvider
from app.ai.providers.factory import get_embedding_provider
from app.ai.providers.fake import FakeEmbeddingProvider
from app.ai.providers.openai import OpenAIEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "get_embedding_provider",
]
