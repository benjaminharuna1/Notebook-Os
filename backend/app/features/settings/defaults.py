DEVICE_TIERS = {
    "low": {
        "chunk_size": 512,
        "chunk_overlap": 64,
        "default_llm": "llama3.2:1b",
        "ollama_model": "llama3.2:1b",
        "embedding_provider": "fastembed",
        "embedding_model": "all-MiniLM-L6-v2",
        "max_tokens": 512,
    },
    "medium": {
        "chunk_size": 1024,
        "chunk_overlap": 128,
        "default_llm": "llama3.2:3b",
        "ollama_model": "llama3.2:3b",
        "embedding_provider": "fastembed",
        "embedding_model": "all-MiniLM-L6-v2",
        "max_tokens": 2048,
    },
    "high": {
        "chunk_size": 1024,
        "chunk_overlap": 128,
        "default_llm": "llama3.2:8b",
        "ollama_model": "llama3.2:8b",
        "embedding_provider": "ollama",
        "embedding_model": "nomic-embed-text",
        "max_tokens": 4096,
    },
}

CLOUD_DEFAULT_MODELS = {
    "openai_model": "gpt-4o-mini",
    "anthropic_model": "claude-3-5-haiku-latest",
    "google_model": "gemini-2.0-flash",
}


def get_default_settings(device_tier: str = "medium") -> dict:
    tier = DEVICE_TIERS.get(device_tier, DEVICE_TIERS["medium"])
    return {
        "chunk_size": tier["chunk_size"],
        "chunk_overlap": tier["chunk_overlap"],
        "default_llm": tier["default_llm"],
        "default_embedding_model": tier["embedding_model"],
        "embedding_backend": tier["embedding_provider"],
        "provider": "ollama",
        "local_model": tier["default_llm"],
        "device_tier": device_tier if device_tier in DEVICE_TIERS else "medium",
        "embedding_provider": tier["embedding_provider"],
        "embedding_model": tier["embedding_model"],
        "cloud_enabled": False,
        "openai_api_key": "",
        "anthropic_api_key": "",
        "google_api_key": "",
        **CLOUD_DEFAULT_MODELS,
        "ollama_model": tier["ollama_model"],
        "max_tokens": tier["max_tokens"],
        "temperature": 0.7,
        "max_concurrent_actions": 2,
    }
