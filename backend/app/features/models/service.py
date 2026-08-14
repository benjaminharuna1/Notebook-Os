from app.core.config import settings
from app.features.models.catalog import CLOUD_MODEL_PRESETS, get_recommendations
from app.features.models.repository import ModelRepository
from app.features.models.downloads import get_downloads
from app.features.models.providers.ollama import OllamaProvider
from app.features.models.providers.local import LocalLLMProvider
from app.features.models.providers.openai import OpenAIProvider
from app.features.models.providers.anthropic import AnthropicProvider
from app.features.models.providers.google import GoogleProvider
from app.features.settings.service import SettingsService
from app.shared.id_utils import generate_id


class ModelService:
    def __init__(self, db, settings_dict: dict | None = None):
        self.db = db
        self.settings_dict = settings_dict or {}
        if db:
            self.repo = ModelRepository(db)
            self.settings_service = SettingsService(db)

    def list_models(self, user_id: str):
        user_settings = self.settings_service.get_settings(user_id).settings
        available = []

        for m in self.list_ollama_available().get("models", []):
            available.append({
                "id": f"ollama:{m}",
                "name": m,
                "provider": "ollama",
                "model_id": m,
                "source": "local",
            })

        for filename in self._local_gguf_files():
            available.append({
                "id": f"local:{filename}",
                "name": filename,
                "provider": "local",
                "model_id": filename,
                "source": "local",
            })

        if settings.CLOUD_ENABLED and user_settings.get("cloud_enabled", False):
            for provider in ("openai", "anthropic", "google"):
                api_key = user_settings.get(f"{provider}_api_key", "")
                model = user_settings.get(f"{provider}_model", "")
                if api_key and model:
                    available.append({
                        "id": f"{provider}:{model}",
                        "name": model,
                        "provider": provider,
                        "model_id": model,
                        "source": "cloud",
                    })

        return {
            "available": available,
            "active": self.get_active_model(user_id),
        }

    def switch_model(self, user_id: str, model_id: str):
        if ":" not in model_id:
            raise ValueError("Invalid model id — expected provider:model")
        provider, m_id = model_id.split(":", 1)

        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE model_configs SET is_active = 0 WHERE user_id = ?",
            (user_id,),
        )

        existing = cursor.execute(
            "SELECT id FROM model_configs WHERE user_id = ? AND provider = ? AND model_id = ?",
            (user_id, provider, m_id),
        ).fetchone()

        if existing:
            cursor.execute(
                "UPDATE model_configs SET is_active = 1 WHERE id = ?",
                (existing["id"],),
            )
        else:
            mid = generate_id()
            cursor.execute(
                """INSERT INTO model_configs (id, user_id, name, provider, model_id, is_active, is_default, config)
                   VALUES (?, ?, ?, ?, ?, 1, 0, '{}')""",
                (mid, user_id, m_id, provider, m_id),
            )
        self.db.commit()
        return {"success": True, "active_model_id": model_id}

    def get_active_model(self, user_id: str):
        row = self.repo.get_active(user_id)
        if not row:
            row = self._seed_default_model(user_id)
        if not row:
            return None
        d = dict(row)
        d["id"] = f"{d['provider']}:{d['model_id']}"
        d["source"] = "local" if d["provider"] in ("ollama", "local") else "cloud"
        return d

    @staticmethod
    def _local_gguf_files() -> list:
        """GGUF files already present in LOCAL_MODELS_DIR, usable as local chat models.

        Files that are catalog embedding models (e.g. the nomic-embed GGUF) are
        excluded — they can't generate chat responses.
        """
        import os

        from app.features.models.catalog import HF_BY_KEY

        embedding_files = {
            m["filename"] for m in HF_BY_KEY.values() if m["kind"] == "embedding"
        }
        models_dir = os.path.abspath(settings.LOCAL_MODELS_DIR)
        try:
            files = sorted(
                f for f in os.listdir(models_dir)
                if f.lower().endswith(".gguf") and f not in embedding_files
            )
        except FileNotFoundError:
            return []
        return files

    def get_provider(self, model_config: dict, user_id: str):
        provider = model_config["provider"]
        if provider == "ollama":
            return OllamaProvider(model_config["model_id"])

        temperature = float(self._user_temperature(user_id))
        max_tokens = int(self._user_max_tokens(user_id))

        if provider == "local":
            return LocalLLMProvider(
                model_config["model_id"],
                temperature=temperature,
                max_tokens=max_tokens,
            )

        if not settings.CLOUD_ENABLED:
            raise ValueError("Cloud models are disabled on this instance")
        if not self.settings_service:
            raise ValueError("Model service has no DB handle")

        user_settings = self.settings_service.get_settings(user_id).settings
        if not user_settings.get("cloud_enabled", False):
            raise ValueError("Enable cloud models in Settings to use this model")

        api_key = user_settings.get(f"{provider}_api_key", "")
        if not api_key:
            raise ValueError(f"No {provider} API key configured — add one in Settings")

        provider_map = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "google": GoogleProvider,
        }
        provider_cls = provider_map.get(provider)
        if not provider_cls:
            raise ValueError(f"Unknown provider: {provider}")
        return provider_cls(
            model_config["model_id"],
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _user_temperature(self, user_id: str) -> float:
        if not self.settings_service:
            return settings.DEFAULT_TEMPERATURE
        return self.settings_service.get_settings(user_id).settings.get(
            "temperature", settings.DEFAULT_TEMPERATURE
        )

    def _user_max_tokens(self, user_id: str) -> int:
        if not self.settings_service:
            return settings.DEFAULT_MAX_TOKENS
        return self.settings_service.get_settings(user_id).settings.get(
            "max_tokens", settings.DEFAULT_MAX_TOKENS
        )

    def list_ollama_available(self):
        try:
            import requests

            response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            return {"models": models}
        except Exception:
            return {"models": []}

    def get_local_status(self, user_id: str):
        user_settings = self.settings_service.get_settings(user_id).settings
        tier = user_settings.get("device_tier", "medium")
        recs = get_recommendations(tier)

        ollama_running = False
        ollama_models = []
        try:
            import requests

            response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
            if response.status_code == 200:
                ollama_running = True
                ollama_models = [m["name"] for m in response.json().get("models", [])]
        except Exception:
            pass

        return {
            "ollama_running": ollama_running,
            "ollama_models": ollama_models,
            "device_tier": tier,
            "recommended_local_model": recs["llm"][0],
            "recommended_embedding": {
                "provider": user_settings.get("embedding_provider", "fastembed"),
                "model": user_settings.get("embedding_model", "all-MiniLM-L6-v2"),
            },
        }

    def get_catalog(self, user_id: str):
        user_settings = self.settings_service.get_settings(user_id).settings
        tier = user_settings.get("device_tier", "medium")
        recs = get_recommendations(tier)
        recs["cloud_presets"] = CLOUD_MODEL_PRESETS
        recs["downloads"] = get_downloads()["downloads"]
        return recs

    def _seed_default_model(self, user_id: str):
        user_settings = self.settings_service.get_settings(user_id).settings
        llm = user_settings.get("default_llm") or settings.DEFAULT_LLM
        provider = user_settings.get("provider") or "ollama"

        model_id = generate_id()
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO model_configs (id, user_id, name, provider, model_id, is_active, is_default, config)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (model_id, user_id, llm, provider, llm, True, True, "{}"),
        )
        self.db.commit()
        return cursor.execute(
            "SELECT * FROM model_configs WHERE id = ? AND user_id = ?",
            (model_id, user_id),
        ).fetchone()
