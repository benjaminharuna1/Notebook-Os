from app.features.documents.repository import DocumentRepository


class DocumentService:
    def __init__(self, db):
        self.repo = DocumentRepository(db)

    def list_documents(self, user_id: str, page: int, limit: int, search: str = "", file_type: str = ""):
        return self.repo.list_documents(user_id, page, limit, search, file_type)

    def get_document(self, document_id: str, user_id: str):
        doc = self.repo.get_by_id(document_id, user_id)
        if not doc:
            raise ValueError("Document not found")

        cursor = self.repo.db.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM chunks WHERE document_id = ?", (document_id,))
        chunk_count = cursor.fetchone()["count"]

        return {**dict(doc), "chunk_count": chunk_count}

    def delete_document(self, document_id: str, user_id: str):
        self.repo.delete(document_id, user_id)
        chroma = self.repo.get_chroma()
        collection = chroma.get_or_create_collection(name="documents")
        collection.delete(where={"document_id": document_id, "user_id": user_id})
        return {"success": True}
