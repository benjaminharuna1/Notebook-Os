from app.shared.id_utils import generate_id


class ChatRepository:
    def __init__(self, db):
        self.db = db

    def create_session(self, session_id: str, user_id: str, title: str, project_id: str | None = None):
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO chat_sessions (id, user_id, project_id, title) VALUES (?, ?, ?, ?)",
            (session_id, user_id, project_id, title),
        )
        self.db.commit()

    def list_sessions(self, user_id: str, project_id: str | None = None):
        cursor = self.db.cursor()
        if project_id:
            cursor.execute(
                "SELECT * FROM chat_sessions WHERE user_id = ? AND project_id = ? ORDER BY updated_at DESC",
                (user_id, project_id),
            )
        else:
            cursor.execute(
                "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
        return [dict(r) for r in cursor.fetchall()]

    def get_session(self, session_id: str, user_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        return cursor.fetchone()

    def get_messages(self, session_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        return [dict(r) for r in cursor.fetchall()]

    def add_message(self, session_id: str, role: str, content: str, sources=None, model_used=None):
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO chat_messages (id, session_id, role, content, sources, model_used)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (generate_id(), session_id, role, content, sources, model_used),
        )
        cursor.execute(
            "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        self.db.commit()

    def delete_session(self, session_id: str, user_id: str):
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        cursor.execute(
            "DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        self.db.commit()

    def update_title(self, session_id: str, title: str):
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE chat_sessions SET title = ? WHERE id = ?",
            (title, session_id),
        )
        self.db.commit()
