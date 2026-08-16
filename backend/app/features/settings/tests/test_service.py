import sqlite3

from app.features.settings.schemas import SettingsUpdate
from app.features.settings.service import SettingsService


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE user_settings (user_id TEXT PRIMARY KEY, settings TEXT)"
    )
    db.execute(
        "INSERT INTO user_settings (user_id, settings) VALUES (?, ?)",
        ("u1", '{"device_tier": "medium", "default_llm": "llama3.2:3b", "ollama_model": "llama3.2:3b"}'),
    )
    db.commit()
    return db


def test_saving_with_unchanged_tier_preserves_chosen_model():
    db = _db()
    svc = SettingsService(db)
    svc.update_settings(
        "u1",
        SettingsUpdate(
            device_tier="medium",
            default_llm="qwen2.5-coder:7b",
            ollama_model="qwen2.5-coder:7b",
        ),
    )
    saved = svc.get_settings("u1").settings
    assert saved["default_llm"] == "qwen2.5-coder:7b"
    assert saved["ollama_model"] == "qwen2.5-coder:7b"


def test_changing_tier_applies_tier_defaults():
    db = _db()
    svc = SettingsService(db)
    svc.update_settings(
        "u1",
        SettingsUpdate(
            device_tier="low",
            default_llm="qwen2.5-coder:7b",
            ollama_model="qwen2.5-coder:7b",
        ),
    )
    saved = svc.get_settings("u1").settings
    assert saved["default_llm"] == "llama3.2:1b"
    assert saved["ollama_model"] == "llama3.2:1b"
