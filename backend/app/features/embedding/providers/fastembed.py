from typing import List

from app.features.embedding.providers.base import BaseEmbeddingProvider

_client = None


def _get_client():
    global _client
    if _client is None:
        from fastembed import TextEmbedding

        _client = TextEmbedding(model_name="all-MiniLM-L6-v2")
    return _client


class FastEmbedProvider(BaseEmbeddingProvider):
    """ONNX embeddings via fastembed. Runs entirely offline after first download.

    First call downloads the small all-MiniLM-L6-v2 model (~25MB) from the
    ONNX model hub; afterwards everything is local and never phones home.
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self.model = model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = _get_client()
        return [vec.tolist() for vec in client.embed(texts)]
