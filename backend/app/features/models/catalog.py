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
        "provider": "ollama",
        "model": "nomic-embed-text",
        "dim": 768,
        "requires": "ollama",
        "note": "Higher quality, needs Ollama installed",
    },
]

CLOUD_MODEL_PRESETS = {
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro"],
}


def get_recommendations(tier: str) -> dict:
    tier = tier if tier in OLLAMA_RECOMMENDATIONS else "medium"
    return {
        "device_tier": tier,
        "llm": OLLAMA_RECOMMENDATIONS[tier],
        "embeddings": EMBEDDING_OPTIONS,
        "cloud": CLOUD_MODEL_PRESETS,
    }
