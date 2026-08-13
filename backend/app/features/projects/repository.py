from app.shared.id_utils import generate_id


class ProjectRepository:
    def __init__(self, db):
        self.db = db

    def create(self, project_id: str, user_id: str, name: str, description: str = ""):
        self.db.execute(
            "INSERT INTO projects (id, user_id, name, description) VALUES (?, ?, ?, ?)",
            (project_id, user_id, name, description),
        )
        self.db.commit()

    def list(self, user_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM documents d WHERE d.project_id = p.id) AS doc_count
               FROM projects p
               WHERE p.user_id = ?
               ORDER BY p.updated_at DESC""",
            (user_id,),
        )
        return [dict(r) for r in cursor.fetchall()]

    def get(self, project_id: str, user_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM documents d WHERE d.project_id = p.id) AS doc_count
               FROM projects p
               WHERE p.id = ? AND p.user_id = ?""",
            (project_id, user_id),
        )
        return cursor.fetchone()

    def update(self, project_id: str, user_id: str, name=None, description=None):
        cursor = self.db.cursor()
        cursor.execute(
            """UPDATE projects
               SET name = COALESCE(?, name),
                   description = COALESCE(?, description),
                   updated_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (name, description, project_id, user_id),
        )
        self.db.commit()

    def delete(self, project_id: str, user_id: str):
        self.db.execute(
            "DELETE FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        )
        self.db.commit()

    def list_documents(self, project_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT id, file_path FROM documents WHERE project_id = ?",
            (project_id,),
        )
        return cursor.fetchall()


def new_project_id() -> str:
    return generate_id()
