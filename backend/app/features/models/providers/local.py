import json
import os
import queue
import threading
from typing import AsyncGenerator, List

from app.core.config import settings
from app.features.models.providers.base import BaseLLMProvider
from app.shared.logger import logger

_model_lock = threading.Lock()
_llm_instance = None


def get_local_model_path(model_id: str) -> str:
    """Resolve a GGUF filename (or relative path) inside LOCAL_MODELS_DIR."""
    models_dir = os.path.abspath(settings.LOCAL_MODELS_DIR)
    candidate = os.path.join(models_dir, model_id)
    if os.path.isfile(candidate):
        return candidate
    # Allow absolute paths too
    if os.path.isfile(model_id):
        return model_id
    raise FileNotFoundError(
        f"Local model '{model_id}' not found in {models_dir}. "
        f"Place the GGUF file there, or run `ollama pull {model_id}` and switch providers."
    )


def _load_llm(model_path: str):
    """Lazy-load a single shared Llama instance (module-level singleton)."""
    global _llm_instance
    with _model_lock:
        if _llm_instance is not None:
            return _llm_instance
        try:
            from llama_cpp import Llama
        except ImportError as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "llama-cpp-python is not installed. Run: uv pip install llama-cpp-python"
            ) from exc

        logger.info("Loading local LLM from %s", model_path)
        _llm_instance = Llama(
            model_path=model_path,
            n_ctx=settings.LLAMA_CONTEXT_SIZE,
            n_threads=settings.LLAMA_THREADS,
            verbose=False,
        )
        return _llm_instance


def reset_llm():
    """Drop the cached model (used in tests)."""
    global _llm_instance
    _llm_instance = None


class LocalLLMProvider(BaseLLMProvider):
    """Runs a GGUF model in-process via llama-cpp-python, streaming tokens.

    llama.cpp generation is synchronous, so the blocking call runs in a worker
    thread and tokens are pumped into a queue; the async generator reads from
    the queue so the event loop (and the SSE stream) stays responsive.
    """

    def __init__(self, model_id: str, **kwargs):
        super().__init__(model_id)
        self.max_tokens = kwargs.pop("max_tokens", settings.LLAMA_MAX_TOKENS)
        self.temperature = kwargs.pop("temperature", settings.DEFAULT_TEMPERATURE)
        self.extra = kwargs

    async def stream_chat(self, prompt: str, messages: List[dict]) -> AsyncGenerator[str, None]:
        model_path = get_local_model_path(self.model_id)
        llm = _load_llm(model_path)

        llm_messages = [{"role": "system", "content": prompt}]
        for m in messages:
            llm_messages.append({"role": m["role"], "content": m["content"]})

        q: "queue.Queue" = queue.Queue()
        done = threading.Event()

        def _generate():
            try:
                stream = llm.create_chat_completion(
                    messages=llm_messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=True,
                )
                for part in stream:
                    delta = part["choices"][0]["delta"]
                    token = delta.get("content")
                    if token:
                        q.put(token)
            except Exception as exc:  # surface errors to the async side
                q.put(exc)
            finally:
                done.set()

        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()

        while not done.is_set() or not q.empty():
            try:
                item = q.get(timeout=0.1)
            except queue.Empty:
                continue
            if isinstance(item, Exception):
                raise item
            yield item

        thread.join(timeout=1)
