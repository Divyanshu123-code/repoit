"""AI Provider interfaces and implementations (P2-02, P2-05, Hard Rule 7).

All vendor and testing providers for LLM completions and embeddings reside here.
"""

from app.ai.providers.base import EmbeddingProvider, LLMProvider
from app.ai.providers.factory import get_embedding_provider, get_llm_provider
from app.ai.providers.fake import FakeEmbeddingProvider
from app.ai.providers.fake_llm import FakeLLMProvider
from app.ai.providers.openai import OpenAIEmbeddingProvider
from app.ai.providers.openai_llm import OpenAILLMProvider

__all__ = [
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "FakeLLMProvider",
    "LLMProvider",
    "OpenAIEmbeddingProvider",
    "OpenAILLMProvider",
    "get_embedding_provider",
    "get_llm_provider",
]
