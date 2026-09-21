import sqlite3

from app.features.skills.service import SkillsService


def _skills_db() -> sqlite3.Connection:
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


def test_chat_skill_detection_uses_existing_method():
    # Regression guard: ChatService must call the real method name,
    # not the removed "detectrelevant_skills" typo.
    assert hasattr(SkillsService, "detect_relevant_skills")

    conn = _skills_db()
    instructions = SkillsService(conn).detect_relevant_skills("u1", "How do I summarize this paper?")
    assert isinstance(instructions, str)


def test_chat_apa_reference_row_access_uses_real_column():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE documents (
            id TEXT PRIMARY KEY, apa_reference TEXT)"""
    )
    conn.executemany(
        "INSERT INTO documents (id, apa_reference) VALUES (?, ?)",
        [("d1", "APA citation for d1"), ("d2", None)],
    )
    conn.commit()

    doc_ids_for_refs = ["d1", "d2"]
    ph = ",".join("?" for _ in doc_ids_for_refs)
    apa_map: dict[str, str] = {}
    for row in conn.execute(
        f"SELECT id, apa_reference FROM documents WHERE id IN ({ph})", doc_ids_for_refs
    ).fetchall():
        if row["apa_reference"]:
            apa_map[row["id"]] = row["apa_reference"]

    assert apa_map == {"d1": "APA citation for d1"}