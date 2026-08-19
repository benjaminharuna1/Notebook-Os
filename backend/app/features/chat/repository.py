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

    def get_messages(self, session_id: str, limit: int | None = None):
        cursor = self.db.cursor()
        if limit:
            cursor.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            )
            rows = list(reversed(cursor.fetchall()))
        else:
            cursor.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

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

    def delete_messages_from(self, session_id: str, message_id: str):
        """Delete a message and all messages after it in the session, using
        SQLite rowid ordering to avoid timestamp collision issues."""
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT rowid FROM chat_messages WHERE id = ? AND session_id = ?",
            (message_id, session_id),
        )
        row = cursor.fetchone()
        if not row:
            return
        cursor.execute(
            "DELETE FROM chat_messages WHERE session_id = ? AND rowid >= ?",
            (session_id, row["rowid"]),
        )
        self.db.commit()

    def update_message_content(self, message_id: str, content: str):
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE chat_messages SET content = ? WHERE id = ?",
            (content, message_id),
        )
        self.db.commit()

    def get_recent_project_chats(
        self, project_id: str, exclude_session_id: str, limit: int = 10
    ) -> list[dict]:
        """Get recent user-assistant message pairs from OTHER sessions in the same
        project.  Returns up to ``limit`` pairs (most recent first) so the LLM has
        awareness of prior conversations."""
        if not project_id:
            return []
        cursor = self.db.cursor()
        cursor.execute(
            """SELECT cm.role, cm.content, cs.title AS session_title, cs.id AS session_id
               FROM chat_messages cm
               JOIN chat_sessions cs ON cs.id = cm.session_id
               WHERE cs.project_id = ?
                 AND cs.id != ?
                 AND cm.role IN ('user', 'assistant')
               ORDER BY cm.created_at DESC
               LIMIT ?""",
            (project_id, exclude_session_id, limit * 2),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        rows.reverse()
        return rows

    # --- project memory (accumulated learning) --------------------------------

    def add_project_memory(self, project_id: str, key: str, value: str, source: str = "chat"):
        """Store a piece of learned knowledge for a project."""
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO project_memory (id, project_id, key, value, source)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(project_id, key) DO UPDATE SET
                 value = excluded.value,
                 updated_at = datetime('now')""",
            (generate_id(), project_id, key, value, source),
        )
        self.db.commit()

    def get_project_memories(self, project_id: str, limit: int = 30) -> list[dict]:
        """Retrieve accumulated memories for a project."""
        cursor = self.db.cursor()
        cursor.execute(
            """SELECT key, value, source, created_at
               FROM project_memory
               WHERE project_id = ?
               ORDER BY updated_at DESC
               LIMIT ?""",
            (project_id, limit),
        )
        return [dict(r) for r in cursor.fetchall()]

    def search_project_memory(self, project_id: str, query: str) -> list[dict]:
        """Search project memory by key or value."""
        cursor = self.db.cursor()
        like = f"%{query}%"
        cursor.execute(
            """SELECT key, value, source
               FROM project_memory
               WHERE project_id = ? AND (key LIKE ? COLLATE NOCASE OR value LIKE ? COLLATE NOCASE)
               ORDER BY updated_at DESC LIMIT 10""",
            (project_id, like, like),
        )
        return [dict(r) for r in cursor.fetchall()]
