import json
import os
import re

from app.core.config import settings
from app.shared.logger import logger

OLLAMA_RECOMMENDATIONS = {
    "low": ["llama3.2:1b", "qwen2.5:0.5b"],
    "medium": ["llama3.2:3b", "qwen2.5:3b"],
    "high": ["llama3.2:8b", "qwen2.5:7b"],
}

EMBEDDING_OPTIONS = [
    {
        "provider": "fastembed",
        "model": "all-MiniLM-L6-v2",
        "dim": 384,
        "requires": "none",
        "note": "ONNX — runs on any device, no Ollama needed",
    },
    {
        "provider": "fastembed",
        "model": "bge-small-en-v1.5",
        "dim": 384,
        "requires": "none",
        "note": "ONNX — better retrieval quality than MiniLM",
    },
    {
        "provider": "fastembed",
        "model": "nomic-embed-text-v1.5",
        "dim": 768,
        "requires": "none",
        "note": "ONNX — 768-dim, high quality, auto-downloads",
    },
    {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "dim": 768,
        "requires": "ollama",
        "note": "Higher quality, needs Ollama installed",
    },
    {
        "provider": "local",
        "model": "nomic-embed-text-v1.5.Q4_K_M.gguf",
        "dim": 768,
        "requires": "download",
        "note": "GGUF via llama.cpp — downloads from HuggingFace, no Ollama",
    },
]

CLOUD_MODEL_PRESETS = {
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro"],
}

# Models that can be pulled straight from HuggingFace Hub into the local
# models directory (LOCAL_MODELS_DIR) — no manual file placement needed.
# GGUF chat models run in-process via llama-cpp-python.
HF_MODELS = [
    {
        "key": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "name": "Qwen 2.5 0.5B Instruct (Q4)",
        "kind": "chat",
        "tier": "low",
        "repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size_label": "~400 MB",
        "note": "Tiny and fast — good for low-end laptops",
    },
    {
        "key": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "name": "Qwen 2.5 3B Instruct (Q4)",
        "kind": "chat",
        "tier": "medium",
        "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "size_label": "~2 GB",
        "note": "Balanced speed and quality — default choice",
    },
    {
        "key": "qwen2.5-7b-instruct-q3_k_m.gguf",
        "name": "Qwen 2.5 7B Instruct (Q3)",
        "kind": "chat",
        "tier": "high",
        "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "filename": "qwen2.5-7b-instruct-q3_k_m.gguf",
        "size_label": "~3.6 GB",
        "note": "Best local quality; needs ~8 GB RAM",
    },
    {
        "key": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "name": "Llama 3.1 8B Instruct (Q4)",
        "kind": "chat",
        "tier": "high",
        "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "size_label": "~4.9 GB",
        "note": "Strong reasoning; needs ~10 GB RAM",
    },
    {
        "key": "nomic-embed-text-v1.5.Q4_K_M.gguf",
        "name": "Nomic Embed 1.5 (Q4)",
        "kind": "embedding",
        "tier": "any",
        "repo": "nomic-ai/nomic-embed-text-v1.5-GGUF",
        "filename": "nomic-embed-text-v1.5.Q4_K_M.gguf",
        "size_label": "~55 MB",
        "note": "Local embedding model (768-dim) — no Ollama",
    },
]

HF_BY_KEY = {m["key"]: m for m in HF_MODELS}


def get_recommendations(tier: str) -> dict:
    tier = tier if tier in OLLAMA_RECOMMENDATIONS else "medium"
    return {
        "device_tier": tier,
        "llm": OLLAMA_RECOMMENDATIONS[tier],
        "embeddings": EMBEDDING_OPTIONS,
        "cloud": CLOUD_MODEL_PRESETS,
    }


# ---------------------------------------------------------------------------
# Custom model registry — user-added HuggingFace GGUF models
# ---------------------------------------------------------------------------

CUSTOM_MODELS_FILENAME = "custom_models.json"

# RAM multiplier per quantization level (file_size × multiplier ≈ RAM needed)
_QUANT_RAM_MULTIPLIERS = {
    "q2": 0.8,
    "q3": 1.0,
    "q4": 1.2,
    "q5": 1.5,
    "q6": 1.8,
    "q8": 2.0,
    "f16": 3.0,
    "fp16": 3.0,
}


def _custom_models_path() -> str:
    return os.path.join(
        os.path.abspath(settings.LOCAL_MODELS_DIR), CUSTOM_MODELS_FILENAME
    )


def load_custom_models() -> list[dict]:
    path = _custom_models_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        logger.warning("Failed to load custom models from %s", path)
        return []


def save_custom_models(models: list[dict]):
    path = _custom_models_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2)


def register_custom_model(entry: dict):
    models = load_custom_models()
    key = entry["key"]
    models = [m for m in models if m.get("key") != key]
    models.append(entry)
    save_custom_models(models)
    logger.info("Registered custom model: %s", key)


def remove_custom_model(key: str) -> bool:
    models = load_custom_models()
    before = len(models)
    models = [m for m in models if m.get("key") != key]
    if len(models) < before:
        save_custom_models(models)
        # Also remove the GGUF file from disk
        for entry in models:
            if entry.get("key") == key:
                break
        # Find the filename from the old list
        old_models = [m for m in load_custom_models() if m.get("key") != key]
        # Actually we need the filename from the removed entry
        # Reload to find it
        removed = [m for m in models if m.get("key") == key]
        if removed:
            filename = removed[0].get("filename", "")
            filepath = os.path.join(
                os.path.abspath(settings.LOCAL_MODELS_DIR), filename
            )
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass
        logger.info("Removed custom model: %s", key)
        return True
    return False


def parse_hf_url(url: str) -> dict | None:
    """Parse a HuggingFace URL into repo and filename.

    Supported formats:
      https://huggingface.co/{owner}/{repo}/resolve/main/{filename}
      https://huggingface.co/{owner}/{repo}/blob/main/{filename}
    """
    pattern = r"https?://huggingface\.co/([^/]+)/([^/]+)/(?:resolve|blob)/([^/]+)/(.+)"
    m = re.match(pattern, url.strip())
    if not m:
        return None
    owner, repo, _branch, filename = m.groups()
    return {
        "repo": f"{owner}/{repo}",
        "filename": filename,
        "url": url.strip(),
    }


def estimate_ram_gb(file_bytes: int, filename: str) -> float:
    """Estimate RAM needed (GB) based on file size and quantization level."""
    base_gb = file_bytes / (1024 ** 3)
    lower = filename.lower()
    for quant, mult in sorted(_QUANT_RAM_MULTIPLIERS.items(), key=lambda x: -len(x[0])):
        if quant in lower:
            return round(base_gb * mult, 1)
    # Default multiplier if no quantization detected
    return round(base_gb * 1.2, 1)


def make_custom_model_key(filename: str) -> str:
    """Generate a stable key from a GGUF filename."""
    return f"custom_{filename}"


def get_all_hf_models() -> dict:
    """Return merged catalog + custom models as {key: entry} dict."""
    merged = dict(HF_BY_KEY)
    for entry in load_custom_models():
        merged[entry["key"]] = entry
    return merged
