from app.shared.id_utils import generate_id

MAX_CONCEPT_LENGTH = 100


class TrackedConceptsService:
    """Persists concepts/themes a user wants to track on a project's graph."""

    def __init__(self, db):
        self.db = db

    def list(self, user_id: str, project_id: str) -> list:
        self._require_project(user_id, project_id)
        rows = self.db.execute(
            """SELECT id, project_id, concept, created_at FROM tracked_concepts
               WHERE user_id = ? AND project_id = ?
               ORDER BY created_at ASC""",
            (user_id, project_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def add(self, user_id: str, project_id: str, concept: str) -> dict:
        self._require_project(user_id, project_id)
        concept = concept.strip()
        if not concept:
            raise ValueError("Concept cannot be empty")
        if len(concept) > MAX_CONCEPT_LENGTH:
            raise ValueError(f"Concept is too long (max {MAX_CONCEPT_LENGTH} characters)")

        existing = self.db.execute(
            """SELECT id FROM tracked_concepts
               WHERE user_id = ? AND project_id = ? AND LOWER(concept) = LOWER(?)""",
            (user_id, project_id, concept),
        ).fetchone()
        if existing:
            return self._get(existing["id"])

        concept_id = generate_id()
        self.db.execute(
            "INSERT INTO tracked_concepts (id, user_id, project_id, concept) VALUES (?, ?, ?, ?)",
            (concept_id, user_id, project_id, concept),
        )
        self.db.commit()
        return self._get(concept_id)

    def remove(self, user_id: str, concept_id: str) -> bool:
        cursor = self.db.execute(
            "DELETE FROM tracked_concepts WHERE id = ? AND user_id = ?",
            (concept_id, user_id),
        )
        self.db.commit()
        return cursor.rowcount > 0

    def _require_project(self, user_id: str, project_id: str) -> None:
        row = self.db.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
        if not row:
            raise ValueError("Project not found")

    def _get(self, concept_id: str) -> dict:
        row = self.db.execute(
            """SELECT id, project_id, concept, created_at FROM tracked_concepts
               WHERE id = ?""",
            (concept_id,),
        ).fetchone()
        return dict(row) if row else None
