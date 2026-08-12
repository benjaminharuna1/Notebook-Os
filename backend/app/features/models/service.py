import json
import requests

from app.core.config import settings
from app.features.models.repository import ModelRepository
from app.features.models.providers.ollama import OllamaProvider
from app.features.models.providers.openai import OpenAIProvider
from app.features.models.providers.anthropic import AnthropicProvider
from app.features.models.providers.google import GoogleProvider
from app.features.settings.service import SettingsService
from app.shared.id_utils import generate_id


class ModelService:
    def __init__(self, db):
        self.db = db
        if db:
            self.repo = ModelRepository(db)
            self.settings_service = SettingsService(db)

    def list_models(self, user_id: str):
        models = self.repo.list_all(user_id)
        active = self.repo.get_active(user_id)
        return {
            "available": [dict(m) for m in models],
            "active": dict(active) if active else None,
        }

    def switch_model(self, user_id: str, model_id: str):
        self.repo.deactivate_all(user_id)
        self.repo.set_active(model_id, user_id)
        return {"success": True, "active_model_id": model_id}

    def get_active_model(self, user_id: str):
        model = self.repo.get_active(user_id)
        if not model:
            model = self._seed_default_model(user_id)
        return dict(model)

    def get_provider(self, model_config: dict):
        provider_map = {
            "ollama": OllamaProvider,
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "google": GoogleProvider,
        }
        provider_cls = provider_map.get(model_config["provider"])
        if not provider_cls:
            raise ValueError(f"Unknown provider: {model_config['provider']}")
        return provider_cls(model_config["model_id"])

    def list_ollama_available(self):
        try:
            response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            return {"models": models}
        except requests.RequestException:
            return {"models": []}

    def _seed_default_model(self, user_id: str):
        user_settings = self.settings_service.get_settings(user_id).settings
        llm = user_settings.get("default_llm", settings.DEFAULT_LLM)
        provider = user_settings.get("provider", "ollama")

        model_id = generate_id()
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO model_configs (id, user_id, name, provider, model_id, is_active, is_default, config)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (model_id, user_id, llm, provider, llm, True, True, json.dumps({"temperature": 0.7, "max_tokens": 2048})),
        )
        self.db.commit()
        return dict(
            cursor.execute(
                "SELECT * FROM model_configs WHERE id = ? AND user_id = ?",
                (model_id, user_id),
            ).fetchone()
        )
