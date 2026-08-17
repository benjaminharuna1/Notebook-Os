import json

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Notebook AI OS"
    APP_VERSION: str = "0.1.0"
    # One or more allowed browser origins. Accepts either a comma-separated
    # string (`http://localhost:5173,http://localhost:5174`) or a JSON list
    # (`["http://localhost:5173","http://localhost:5174"]`).
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        text = self.CORS_ORIGINS.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in text.split(",") if item.strip()]

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/notebook.db"
    CHROMA_DB_PATH: str = "./data/chroma_db"
    UPLOAD_DIR: str = "./data/uploads"
    PROCESSED_DIR: str = "./data/processed"

    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Local-first inference (llama-cpp-python)
    LOCAL_MODELS_DIR: str = "./models"
    # Which embedding backend to use by default: "local" (llama-cpp, no Ollama) or "ollama"
    EMBEDDING_BACKEND: str = "fastembed"
    # Default local GGUF models (filenames inside LOCAL_MODELS_DIR)
    LOCAL_LLM_MODEL: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    LOCAL_EMBEDDING_MODEL: str = "nomic-embed-text-v1.5.Q4_K_M.gguf"
    # llama-cpp tuning
    LLAMA_THREADS: int = 4
    LLAMA_CONTEXT_SIZE: int = 4096
    LLAMA_MAX_TOKENS: int = 512

    # Defaults (used as fallback when a user has no settings row yet)
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 128
    DEFAULT_LLM: str = "llama3.2:3b"
    DEFAULT_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    DEFAULT_EMBEDDING_PROVIDER: str = "fastembed"
    DEFAULT_PROVIDER: str = "ollama"
    DEFAULT_TEMPERATURE: float = 0.3
    DEFAULT_MAX_TOKENS: int = 2048

    # Cloud model support. Users opt in per-account in Settings; set this to
    # false to hard-disable cloud models server-wide.
    CLOUD_ENABLED: bool = True

    # Uploads
    MAX_UPLOAD_SIZE_MB: int = 25
    # Chunks per embedding batch in the background ingestion pipeline
    EMBED_BATCH_SIZE: int = 16

    # Rate limiting (per client IP)
    RATE_LIMIT_MAX_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Skill catalog directory. Leave empty to use the app-level skills folder
    # (backend/skills); point elsewhere (or at a registry mirror) to serve a
    # different set of skills.
    SKILLS_CATALOG_DIR: str = ""

    JWT_SECRET_KEY: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    # Session lifetime in minutes. Kept at 1 day so it matches the auth cookie's
    # 24h max-age; a shorter JWT than the cookie would force re-logins.
    JWT_EXPIRE_MINUTES: int = 1440

    # Mark the session cookie Secure when serving over HTTPS.
    COOKIE_SECURE: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
