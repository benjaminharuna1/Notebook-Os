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
