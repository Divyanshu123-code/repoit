"""Factory for resolving and instantiating embedding providers (P2-02)."""

from app.ai.providers.base import EmbeddingProvider
from app.ai.providers.fake import FakeEmbeddingProvider
from app.ai.providers.openai import OpenAIEmbeddingProvider
from app.core.config import Settings, get_settings


def get_embedding_provider(
    provider_type: str | None = None,
    settings: Settings | None = None,
) -> EmbeddingProvider:
    """Instantiate the configured EmbeddingProvider."""
    app_settings = settings or get_settings()
    selected_type = (provider_type or app_settings.EMBEDDING_PROVIDER).strip().lower()

    if selected_type == "openai":
        if not app_settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required when using the 'openai' embedding provider."
            )
        return OpenAIEmbeddingProvider(
            api_key=app_settings.OPENAI_API_KEY,
            model_name=app_settings.EMBEDDING_MODEL,
            dimension=app_settings.EMBEDDING_DIMENSION,
            base_url=app_settings.OPENAI_BASE_URL,
        )

    if selected_type == "fake":
        return FakeEmbeddingProvider(
            dimension=app_settings.EMBEDDING_DIMENSION,
            model_name=app_settings.EMBEDDING_MODEL,
        )

    raise ValueError(
        f"Unsupported embedding provider: '{selected_type}'. Supported providers are: 'fake', 'openai'."
    )
