from app.core.database import get_chroma_client


class DocumentRepository:
    def __init__(self, db):
        self.db = db

    def list_documents(
        self,
        user_id: str,
        page: int,
        limit: int,
        search: str = "",
        file_type: str = "",
        project_id: str | None = None,
    ):
        cursor = self.db.cursor()
        conditions = ["user_id = ?"]
        params = [user_id]

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if search:
            conditions.append("title LIKE ?")
            params.append(f"%{search}%")
        if file_type:
            conditions.append("file_type = ?")
            params.append(file_type)

        where = "WHERE " + " AND ".join(conditions)
        offset = (page - 1) * limit

        cursor.execute(f"SELECT COUNT(*) as total FROM documents {where}", params)
        total = cursor.fetchone()["total"]

        cursor.execute(
            f"SELECT * FROM documents {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        rows = cursor.fetchall()

        return {"documents": [dict(r) for r in rows], "total": total, "page": page}

    def get_by_id(self, document_id: str, user_id: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
        return cursor.fetchone()

    def delete(self, document_id: str, user_id: str):
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        cursor.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
        self.db.commit()

    def get_chroma(self):
        return get_chroma_client()
