import sqlite3

import app.features.embedding.service as embedding_service


class _FakeCollection:
    def __init__(self):
        self.added = []

    def add(self, ids, embeddings, metadatas, documents):
        self.added.append(
            {"ids": ids, "embeddings": embeddings, "metadatas": metadatas, "documents": documents}
        )


class _FakeChroma:
    def __init__(self):
        self.collection = _FakeCollection()

    def get_or_create_collection(self, name):
        return self.collection


class _FakeProvider:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


def _chunk(id_, index, content, **kw):
    return {
        "id": id_,
        "document_id": "d1",
        "chunk_index": index,
        "content": content,
        "page_number": kw.get("page_number"),
        "char_start": kw.get("char_start"),
        "char_end": kw.get("char_end"),
        "token_count": kw.get("token_count", 0),
    }


def test_embed_chunks_persists_chunks_to_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE chunks (
            id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, content TEXT,
            page_number INTEGER, char_start INTEGER, char_end INTEGER,
            token_count INTEGER, embedded_at DATETIME)"""
    )
    conn.close()

    chroma = _FakeChroma()
    monkeypatch.setattr(embedding_service, "get_chroma_client", lambda: chroma)
    monkeypatch.setattr(
        embedding_service,
        "get_sqlite_connection",
        lambda: sqlite3.connect(db_path),
    )

    service = embedding_service.EmbeddingService()
    service.provider = _FakeProvider()

    chunks = [
        _chunk("c1", 0, "Neural Networks power modern AI."),
        _chunk("c2", 1, "Database indexing improves query performance.", page_number=2),
    ]
    service.embed_chunks(chunks, document_id="d1", user_id="u1", project_id="p1", title="Doc")

    assert chroma.collection.added, "Chroma should receive the batch"
    assert chroma.collection.added[0]["metadatas"][0]["project_id"] == "p1"

    db = sqlite3.connect(db_path)
    rows = db.execute("SELECT * FROM chunks ORDER BY chunk_index").fetchall()
    assert [r[2] for r in rows] == [0, 1]
    assert rows[0][1] == "d1"
    assert rows[0][3] == "Neural Networks power modern AI."
    assert rows[1][4] == 2
