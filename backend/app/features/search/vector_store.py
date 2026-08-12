from app.core.database import get_chroma_client


class VectorStore:
    def __init__(self):
        self.client = get_chroma_client()
        self.collection = self.client.get_or_create_collection(name="documents")

    def add(self, ids, embeddings, metadatas, documents):
        self.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def query(self, query_embeddings, n_results=5, where=None):
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

    def delete_by_document(self, document_id: str):
        self.collection.delete(where={"document_id": document_id})
