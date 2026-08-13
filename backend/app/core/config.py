from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Notebook AI OS"
    APP_VERSION: str = "0.1.0"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

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
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_MAX_TOKENS: int = 2048

    # Cloud model support. Users opt in per-account in Settings; set this to
    # false to hard-disable cloud models server-wide.
    CLOUD_ENABLED: bool = True

    # Uploads
    MAX_UPLOAD_SIZE_MB: int = 25

    # Rate limiting (per client IP)
    RATE_LIMIT_MAX_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    JWT_SECRET_KEY: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    # Session lifetime in minutes. Kept at 1 day so it matches the auth cookie's
    # 24h max-age; a shorter JWT than the cookie would force re-logins.
    JWT_EXPIRE_MINUTES: int = 1440

    # Mark the session cookie Secure when serving over HTTPS.
    COOKIE_SECURE: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
