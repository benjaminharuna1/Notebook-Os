import os
import threading
from typing import List

from app.core.config import settings
from app.features.embedding.providers.base import BaseEmbeddingProvider
from app.shared.logger import logger

_embedding_lock = threading.Lock()
_embedding_model = None


def _load_embedding_model(model_path: str):
    global _embedding_model
    with _embedding_lock:
        if _embedding_model is not None:
            return _embedding_model
        try:
            from llama_cpp import Llama
        except ImportError as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "llama-cpp-python is not installed. Run: uv pip install llama-cpp-python"
            ) from exc

        logger.info("Loading local embedding model from %s", model_path)
        _embedding_model = Llama(
            model_path=model_path,
            n_ctx=settings.LLAMA_CONTEXT_SIZE,
            n_threads=settings.LLAMA_THREADS,
            embedding=True,
            verbose=False,
        )
        return _embedding_model


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Embeddings via llama-cpp-python (GGUF, in-process, no Ollama needed)."""

    def __init__(self, model: str = ""):
        self.model = model or settings.LOCAL_EMBEDDING_MODEL

    def _resolve_path(self) -> str:
        models_dir = os.path.abspath(settings.LOCAL_MODELS_DIR)
        candidate = os.path.join(models_dir, self.model)
        if os.path.isfile(candidate):
            return candidate
        if os.path.isfile(self.model):
            return self.model
        raise FileNotFoundError(
            f"Local embedding model '{self.model}' not found in {models_dir}. "
            "Place the GGUF file there, or set EMBEDDING_BACKEND=ollama."
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        model = _load_embedding_model(self._resolve_path())
        results = []
        for text in texts:
            # llama.cpp returns tokens/embeddings per sequence; take the first
            emb = model.create_embedding(text)
            # create_embedding returns {"data": [{"embedding": [...]}]}
            results.append(emb["data"][0]["embedding"])
        return results
