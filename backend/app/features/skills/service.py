import json
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import settings
from app.features.skills.schemas import SkillManifest


def _catalog_dir() -> Path:
    """Directory of available skill manifests. Overridable via settings so a
    remote registry or a user-provided catalog directory can be plugged in.
    Defaults to the project-level backend/skills directory (the app-level
    skills), falling back to the bundled catalog inside the package."""
    if settings.SKILLS_CATALOG_DIR:
        return Path(settings.SKILLS_CATALOG_DIR)
    project_skills = Path(__file__).resolve().parents[3] / "skills"
    if project_skills.is_dir():
        return project_skills
    return Path(__file__).parent / "catalog"


def _manifest_from_markdown(folder: Path) -> SkillManifest:
    """Build a manifest from a `*/SKILL.md` folder. The folder name is the id,
    the first paragraph (before the first `##` section) becomes the
    description, and the full markdown body is injected as the instructions."""
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    description = ""
    for line in text.split("\n## ", 1)[0].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("```"):
            break
        description = f"{description} {line}".strip()
        if len(description) > 160:
            break
    return SkillManifest(
        id=folder.name,
        name=folder.name.replace("-", " ").replace("_", " ").title(),
        description=description or "No description provided.",
        instructions=text,
    )


def load_catalog() -> list[SkillManifest]:
    manifests = []
    catalog_dir = _catalog_dir()
    if not catalog_dir.is_dir():
        return manifests
    for path in sorted(catalog_dir.glob("*.json")):
        try:
            manifests.append(SkillManifest.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            # skip malformed catalog entries rather than breaking the whole app
            continue
    for folder in sorted(p for p in catalog_dir.iterdir() if p.is_dir()):
        if not (folder / "SKILL.md").is_file():
            continue
        try:
            manifests.append(_manifest_from_markdown(folder))
        except Exception:
            # skip malformed markdown skills rather than breaking the whole app
            continue
    return manifests


class SkillsService:
    def __init__(self, db):
        self.db = db

    def _ensure_installed(self, user_id: str) -> None:
        """App-level (catalog) skills are always installed for every user."""
        catalog = load_catalog()
        if not catalog:
            return
        rows = {
            r["skill_id"]
            for r in self.db.execute(
                "SELECT skill_id FROM user_skills WHERE user_id = ?", (user_id,)
            ).fetchall()
        }
        for manifest in catalog:
            if manifest.id in rows:
                continue
            self.db.execute(
                "INSERT INTO user_skills (user_id, skill_id, manifest, enabled) VALUES (?, ?, ?, 1)",
                (user_id, manifest.id, json.dumps(manifest.model_dump())),
            )
        self.db.commit()

    def list_installed(self, user_id: str) -> list[dict]:
        self._ensure_installed(user_id)
        rows = self.db.execute(
            "SELECT skill_id, manifest, enabled, installed_at FROM user_skills WHERE user_id = ? ORDER BY installed_at",
            (user_id,),
        ).fetchall()
        return [
            {
                "skill": json.loads(r["manifest"]),
                "enabled": bool(r["enabled"]),
                "installed_at": r["installed_at"],
            }
            for r in rows
        ]

    def list_catalog(self, user_id: str) -> list[dict]:
        self._ensure_installed(user_id)
        installed = {
            r["skill_id"]
            for r in self.db.execute(
                "SELECT skill_id FROM user_skills WHERE user_id = ?", (user_id,)
            ).fetchall()
        }
        return [
            {"skill": m.model_dump(), "installed": m.id in installed} for m in load_catalog()
        ]

    def install(self, user_id: str, skill_id: str) -> dict:
        manifest = next((m for m in load_catalog() if m.id == skill_id), None)
        if not manifest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill '{skill_id}' not found in catalog",
            )
        self.db.execute(
            """INSERT INTO user_skills (user_id, skill_id, manifest, enabled)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(user_id, skill_id) DO UPDATE SET manifest = excluded.manifest""",
            (user_id, skill_id, json.dumps(manifest.model_dump())),
        )
        self.db.commit()
        return {"success": True}

    def uninstall(self, user_id: str, skill_id: str) -> dict:
        self.db.execute(
            "DELETE FROM user_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, skill_id),
        )
        self.db.commit()
        return {"success": True}

    def set_enabled(self, user_id: str, skill_id: str, enabled: bool) -> dict:
        self.db.execute(
            "UPDATE user_skills SET enabled = ? WHERE user_id = ? AND skill_id = ?",
            (1 if enabled else 0, user_id, skill_id),
        )
        self.db.commit()
        return {"success": True}

    def import_skill(self, user_id: str, manifest: SkillManifest) -> dict:
        already = self.db.execute(
            "SELECT 1 FROM user_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, manifest.id),
        ).fetchone()
        if already:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Skill '{manifest.id}' is already installed",
            )
        if any(m.id == manifest.id for m in load_catalog()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A catalog skill with id '{manifest.id}' already exists",
            )
        self.db.execute(
            "INSERT INTO user_skills (user_id, skill_id, manifest, enabled) VALUES (?, ?, ?, 1)",
            (user_id, manifest.id, json.dumps(manifest.model_dump())),
        )
        self.db.commit()
        return {"success": True}

    def active_instructions(self, user_id: str) -> str:
        self._ensure_installed(user_id)
        rows = self.db.execute(
            "SELECT manifest FROM user_skills WHERE user_id = ? AND enabled = 1",
            (user_id,),
        ).fetchall()
        sections = []
        for r in rows:
            m = json.loads(r["manifest"])
            sections.append(f"## {m['name']}\n{m['instructions']}")
        return "\n\n".join(sections)
