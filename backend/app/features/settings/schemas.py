from pydantic import BaseModel
from typing import Optional


class SettingsResponse(BaseModel):
    settings: dict


class SettingsUpdate(BaseModel):
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    default_llm: Optional[str] = None
    default_embedding_model: Optional[str] = None
    provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_model: Optional[str] = None
    google_model: Optional[str] = None
    ollama_model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
