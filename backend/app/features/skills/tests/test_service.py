import json
import sqlite3

import pytest
from fastapi import HTTPException

from app.core.config import settings
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
    assert "literature-mapping" in ids


def test_load_catalog_supports_markdown_skill_folders(tmp_path, monkeypatch):
    skill_dir = tmp_path / "custom-folder"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# My Markdown Skill\n\nDescription line one. Description line two.\n\n## Rules\n\nDo the thing.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "SKILLS_CATALOG_DIR", str(tmp_path))
    manifests = load_catalog()
    assert len(manifests) == 1
    m = manifests[0]
    assert m.id == "custom-folder"
    assert m.name == "Custom Folder"
    assert "Description line one." in m.description
    assert "Do the thing." in m.instructions


def test_catalog_skills_auto_installed_for_every_user():
    conn = _db()
    service = SkillsService(conn)
    catalog_ids = {m.id for m in load_catalog()}
    for user in ("u1", "u2"):
        installed = service.list_installed(user)
        assert {i["skill"]["id"] for i in installed} == catalog_ids
        assert all(i["enabled"] is True for i in installed)


def test_toggle_enabled_affects_active_instructions():
    conn = _db()
    service = SkillsService(conn)

    assert "Research Workflow" in service.active_instructions("u1")

    service.set_enabled("u1", "research-workflow", False)
    assert "Research Workflow" not in service.active_instructions("u1")
    rw = next(
        i for i in service.list_installed("u1") if i["skill"]["id"] == "research-workflow"
    )
    assert rw["enabled"] is False

    service.set_enabled("u1", "research-workflow", True)
    assert "Research Workflow" in service.active_instructions("u1")


def test_uninstall_catalog_skill_is_reinstalled_on_next_list():
    conn = _db()
    service = SkillsService(conn)
    assert service.list_installed("u1")
    service.uninstall("u1", "research-workflow")
    ids = {i["skill"]["id"] for i in service.list_installed("u1")}
    assert "research-workflow" in ids


def test_catalog_install_unknown_skill_rejected():
    conn = _db()
    with pytest.raises(HTTPException) as excinfo:
        SkillsService(conn).install("u1", "does-not-exist")
    assert excinfo.value.status_code == 404


def test_import_custom_skill_is_per_user():
    conn = _db()
    service = SkillsService(conn)

    assert service.import_skill("u1", _manifest()) == {"success": True}
    assert "custom-skill" in {i["skill"]["id"] for i in service.list_installed("u1")}
    assert "custom-skill" not in {i["skill"]["id"] for i in service.list_installed("u2")}
    assert "Do the thing." in service.active_instructions("u1")
    assert "Do the thing." not in service.active_instructions("u2")

    with pytest.raises(HTTPException) as excinfo:
        service.import_skill("u1", _manifest())
    assert excinfo.value.status_code == 409

    with pytest.raises(HTTPException) as excinfo:
        service.import_skill("u2", _manifest(id="research-workflow"))
    assert excinfo.value.status_code == 409


def test_catalog_flags_installed():
    conn = _db()
    service = SkillsService(conn)
    catalog = service.list_catalog("u1")
    assert len(catalog) == len(load_catalog())
    assert all(c["installed"] for c in catalog)


def test_install_persists_manifest_json():
    conn = _db()
    service = SkillsService(conn)
    service.import_skill("u1", _manifest(tags=["a", "b"]))
    row = conn.execute("SELECT manifest FROM user_skills").fetchone()
    assert json.loads(row["manifest"])["tags"] == ["a", "b"]
