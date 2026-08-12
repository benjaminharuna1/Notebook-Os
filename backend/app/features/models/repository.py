class ModelRepository:
    def __init__(self, db):
        self.db = db

    def list_all(self, user_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM model_configs WHERE user_id = ? ORDER BY is_default DESC",
            (user_id,),
        )
        return cursor.fetchall()

    def get_active(self, user_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM model_configs WHERE user_id = ? AND is_active = 1 LIMIT 1",
            (user_id,),
        )
        return cursor.fetchone()

    def deactivate_all(self, user_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE model_configs SET is_active = 0 WHERE user_id = ?",
            (user_id,),
        )
        self.db.commit()

    def set_active(self, model_id: str, user_id: str):
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE model_configs SET is_active = 1 WHERE id = ? AND user_id = ?",
            (model_id, user_id),
        )
        self.db.commit()
