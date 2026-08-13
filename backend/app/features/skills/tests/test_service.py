import json
import sqlite3

import pytest
from fastapi import HTTPException

from app.features.skills.schemas import SkillManifest
from app.features.skills.service import SkillsService, load_catalog


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE user_skills (
            user_id TEXT NOT NULL, skill_id TEXT NOT NULL, manifest TEXT NOT NULL,
            enabled INTEGER DEFAULT 1, installed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, skill_id))"""
    )
    conn.commit()
    return conn


def _manifest(**overrides) -> SkillManifest:
    base = {
        "id": "custom-skill",
        "name": "Custom Skill",
        "description": "A test skill",
        "instructions": "Do the thing.",
    }
    base.update(overrides)
    return SkillManifest.model_validate(base)


def test_catalog_loads_bundled_skills():
    ids = {m.id for m in load_catalog()}
    assert {"research-workflow", "citation-formatter", "summarize"} <= ids


def test_install_list_enable_uninstall_flow():
    conn = _db()
    service = SkillsService(conn)

    assert service.install("u1", "research-workflow") == {"success": True}
    installed = service.list_installed("u1")
    assert len(installed) == 1
    assert installed[0]["skill"]["id"] == "research-workflow"
    assert installed[0]["enabled"] is True

    service.set_enabled("u1", "research-workflow", False)
    assert service.list_installed("u1")[0]["enabled"] is False

    assert service.active_instructions("u1") == ""
    service.set_enabled("u1", "research-workflow", True)
    instructions = service.active_instructions("u1")
    assert "## Research Workflow" in instructions

    assert service.uninstall("u1", "research-workflow") == {"success": True}
    assert service.list_installed("u1") == []


def test_catalog_install_unknown_skill_rejected():
    conn = _db()
    with pytest.raises(HTTPException) as excinfo:
        SkillsService(conn).install("u1", "does-not-exist")
    assert excinfo.value.status_code == 404


def test_install_is_scoped_per_user():
    conn = _db()
    service = SkillsService(conn)
    service.install("u1", "summarize")
    assert service.list_installed("u2") == []
    assert service.active_instructions("u2") == ""


def test_import_custom_skill():
    conn = _db()
    service = SkillsService(conn)

    assert service.import_skill("u1", _manifest()) == {"success": True}
    installed = service.list_installed("u1")
    assert installed[0]["skill"]["id"] == "custom-skill"
    assert "Do the thing." in service.active_instructions("u1")

    with pytest.raises(HTTPException) as excinfo:
        service.import_skill("u1", _manifest())
    assert excinfo.value.status_code == 409

    with pytest.raises(HTTPException) as excinfo:
        service.import_skill("u2", _manifest(id="research-workflow"))
    assert excinfo.value.status_code == 409


def test_catalog_flags_installed():
    conn = _db()
    service = SkillsService(conn)
    service.install("u1", "summarize")
    catalog = service.list_catalog("u1")
    by_id = {c["skill"]["id"]: c for c in catalog}
    assert by_id["summarize"]["installed"] is True
    assert by_id["research-workflow"]["installed"] is False


def test_install_persists_manifest_json():
    conn = _db()
    service = SkillsService(conn)
    service.import_skill("u1", _manifest(tags=["a", "b"]))
    row = conn.execute("SELECT manifest FROM user_skills").fetchone()
    assert json.loads(row["manifest"])["tags"] == ["a", "b"]
