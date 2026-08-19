from app.shared.id_utils import generate_id


class FeatureRepository:
    def __init__(self, db):
        self.db = db

    def example_query(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT 1")
        return cursor.fetchall()
