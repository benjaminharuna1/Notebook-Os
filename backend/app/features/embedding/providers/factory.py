from app.core.config import settings
from app.features.embedding.providers.base import BaseEmbeddingProvider


def resolve_embedding_provider(settings_dict: dict | None = None) -> BaseEmbeddingProvider:
    """Return the embedding provider for the active embedding configuration.

    Priority: per-user `embedding_provider`/`embedding_model` settings,
    falling back to env (DEFAULT_EMBEDDING_PROVIDER).
    """
    settings_dict = settings_dict or {}
    provider = (
        settings_dict.get("embedding_provider")
        or settings_dict.get("embedding_backend")
        or settings.DEFAULT_EMBEDDING_PROVIDER
    )

    if provider == "ollama":
        from app.features.embedding.providers.ollama import OllamaEmbeddingProvider

        model = settings_dict.get("embedding_model") or settings_dict.get("default_embedding_model") or "nomic-embed-text"
        return OllamaEmbeddingProvider(model=model)

    if provider == "local":
        from app.features.embedding.providers.local import LocalEmbeddingProvider

        model = settings_dict.get("embedding_model") or settings_dict.get("default_embedding_model") or settings.LOCAL_EMBEDDING_MODEL
        return LocalEmbeddingProvider(model=model)

    # Default: fastembed (ONNX, no Ollama required)
    from app.features.embedding.providers.fastembed import FastEmbedProvider

    model = settings_dict.get("embedding_model") or settings_dict.get("default_embedding_model") or settings.DEFAULT_EMBEDDING_MODEL
    return FastEmbedProvider(model=model)


def collection_name_for(provider: str, model: str) -> str:
    """Canonical Chroma collection name per embedding (provider, model)."""
    safe_model = model.replace(":", "_").replace("/", "_").replace("@", "_").replace(".", "_")
    return f"documents__{provider}_{safe_model}"


def resolve_collection_name(settings_dict: dict | None = None) -> str:
    settings_dict = settings_dict or {}
    provider = (
        settings_dict.get("embedding_provider")
        or settings_dict.get("embedding_backend")
        or settings.DEFAULT_EMBEDDING_PROVIDER
    )
    if provider == "ollama":
        model = settings_dict.get("embedding_model") or settings_dict.get("default_embedding_model") or "nomic-embed-text"
        return collection_name_for("ollama", model)
    if provider == "local":
        model = settings_dict.get("embedding_model") or settings_dict.get("default_embedding_model") or settings.LOCAL_EMBEDDING_MODEL
        return collection_name_for("local", model)
    model = settings_dict.get("embedding_model") or settings_dict.get("default_embedding_model") or settings.DEFAULT_EMBEDDING_MODEL
    return collection_name_for("fastembed", model)
