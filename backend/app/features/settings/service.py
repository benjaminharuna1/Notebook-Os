import json

from fastapi import HTTPException, status

from app.features.settings.defaults import DEVICE_TIERS
from app.features.settings.schemas import SettingsResponse, SettingsUpdate


class SettingsService:
    def __init__(self, db):
        self.db = db

    def get_settings(self, user_id: str) -> SettingsResponse:
        cursor = self.db.cursor()
        cursor.execute("SELECT settings FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return SettingsResponse(settings={})
        return SettingsResponse(settings=json.loads(row["settings"]))

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

        # Choosing a device tier also applies that tier's local model defaults
        tier = current.get("device_tier")
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

        cursor.execute(
            "UPDATE user_settings SET settings = ? WHERE user_id = ?",
            (json.dumps(current), user_id),
        )
        self.db.commit()

        return SettingsResponse(settings=current)
