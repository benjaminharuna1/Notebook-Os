import json

from fastapi import HTTPException, status

from app.core.crypto import decrypt_secret, encrypt_secret
from app.features.settings.defaults import DEVICE_TIERS
from app.features.settings.schemas import SettingsResponse, SettingsUpdate

SECRET_SUFFIX = "_api_key"


def _is_secret(key: str) -> bool:
    return key.endswith(SECRET_SUFFIX)


class SettingsService:
    def __init__(self, db):
        self.db = db

    def get_settings(self, user_id: str) -> SettingsResponse:
        cursor = self.db.cursor()
        cursor.execute("SELECT settings FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return SettingsResponse(settings={})
        raw = json.loads(row["settings"])
        return SettingsResponse(settings=self._decrypt(raw))

    @staticmethod
    def _decrypt(data: dict) -> dict:
        return {k: (decrypt_secret(v) if _is_secret(k) else v) for k, v in data.items()}

    @staticmethod
    def _encrypt(data: dict) -> dict:
        return {k: (encrypt_secret(v) if _is_secret(k) else v) for k, v in data.items()}

    def update_settings(self, user_id: str, req: SettingsUpdate) -> SettingsResponse:
        cursor = self.db.cursor()
        cursor.execute("SELECT settings FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if not row:
            cursor.execute(
                "INSERT INTO user_settings (user_id, settings) VALUES (?, ?)",
                (user_id, json.dumps({})),
            )
            self.db.commit()
            current = {}
        else:
            current = json.loads(row["settings"])

        updates = req.model_dump(exclude_unset=True)
        current.update(updates)

        # Choosing a device tier also applies that tier's local model defaults.
        # Only when the tier itself changed in this request — otherwise saving
        # settings would clobber a model the user picked from a dropdown.
        tier = updates.get("device_tier")
        if tier in DEVICE_TIERS:
            t = DEVICE_TIERS[tier]
            current["default_llm"] = t["default_llm"]
            current["ollama_model"] = t["ollama_model"]
            current["chunk_size"] = t["chunk_size"]
            current["chunk_overlap"] = t["chunk_overlap"]
            current["max_tokens"] = t["max_tokens"]
            if tier != "high":
                current["embedding_provider"] = "fastembed"
                current["embedding_model"] = t["embedding_model"]

        stored = self._encrypt(current)

        cursor.execute(
            "UPDATE user_settings SET settings = ? WHERE user_id = ?",
            (json.dumps(stored), user_id),
        )
        self.db.commit()

        return SettingsResponse(settings=current)
