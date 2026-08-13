from app.core.database import get_chroma_client


class VectorStore:
    def __init__(self, collection_name: str = "documents"):
        self.client = get_chroma_client()
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=collection_name)

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


def delete_document_vectors(user_id: str, document_id: str):
    """Delete a document's vectors from every embedding collection.

    Chroma uses one collection per (embedding provider, model), so a document
    may have been embedded under different models over time. Wipe it from all.
    """
    client = get_chroma_client()
    for collection in client.list_collections():
        name = getattr(collection, "name", None)
        if not name or not name.startswith("documents__"):
            continue
        try:
            collection.delete(where={"document_id": document_id})
        except Exception:
            continue
