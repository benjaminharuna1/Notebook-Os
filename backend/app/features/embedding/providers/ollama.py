from typing import List

import requests

from app.core.config import settings
from app.features.embedding.providers.base import BaseEmbeddingProvider


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model: str = "nomic-embed-text"):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = model

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Batch all texts in a single request instead of N round-trips
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["embeddings"]
