from typing import Any, Dict, List

from app.features.embedding.providers.base import BaseEmbeddingProvider

_clients: Dict[str, Any] = {}


def _resolve_model_name(model: str) -> str:
    from fastembed import TextEmbedding

    supported = [m["model"] for m in TextEmbedding.list_supported_models()]
    if model in supported:
        return model
    # Tolerate short names like "all-MiniLM-L6-v2" -> "sentence-transformers/all-MiniLM-L6-v2".
    for full in supported:
        if full.endswith("/" + model):
            return full
    raise ValueError(
        f"Embedding model {model!r} is not supported by fastembed. "
        f"Supported models: {supported}"
    )


class FastEmbedProvider(BaseEmbeddingProvider):
    """ONNX embeddings via fastembed. Runs entirely offline after first download.

    First call downloads the small all-MiniLM-L6-v2 model (~25MB) from the
    ONNX model hub; afterwards everything is local and never phones home.
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self.model = model

    def _get_client(self):
        from fastembed import TextEmbedding

        model = _resolve_model_name(self.model)
        if model not in _clients:
            _clients[model] = TextEmbedding(model_name=model)
        return _clients[model]

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = self._get_client()
        return [vec.tolist() for vec in client.embed(texts)]
