import json
from collections import Counter, defaultdict
from typing import List, Optional, Tuple

from app.features.graph.builder import GraphBuilder, layout_nodes
from app.features.graph.schemas import GraphEdge, GraphNode, GraphResponse
from app.shared.id_utils import generate_id

# Session-scoped cache so repeated graph builds (e.g. while a user tweaks their
# tracked themes) skip re-extracting every chunk. Keys include the document
# set, each chunk's `embedded_at`, and the tracked preferences, so re-indexing
# or preference changes invalidate automatically.
_BUILD_CACHE: dict = {}

# Every generated graph is also persisted to `graph_history` as a checkpoint.
# Page loads serve the most recent checkpoint instead of re-extracting every
# chunk, unless new papers were indexed (fingerprint change) or the user
# explicitly regenerates. Older checkpoints stay available for browsing,
# favouriting, and deletion.
_CREATE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS graph_history (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    project_id  TEXT NOT NULL,
    graph_json  TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    prefs_key   TEXT NOT NULL,
    is_favourite INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""
_CREATE_HISTORY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_graph_history_lookup
ON graph_history(user_id, project_id, created_at)
"""


def _build_key(
    user_id: str,
    project_id: Optional[str],
    doc_ids: List[str],
    depth: int,
    prefs: List[str],
    chunks: List[dict],
) -> Tuple:
    version = tuple((c.get("id"), c.get("embedded_at")) for c in chunks)
    return (user_id, project_id, tuple(doc_ids), depth, tuple(prefs), version)


def _fingerprint(chunks: List[dict]) -> str:
    version = sorted((c.get("document_id"), c.get("id"), c.get("embedded_at") or "") for c in chunks)
    return json.dumps(version)


class GraphService:
    def __init__(self, db):
        self.db = db
        self.builder = GraphBuilder()
        cur = self.db.cursor()
        cur.execute(_CREATE_HISTORY_TABLE)
        cur.execute(_CREATE_HISTORY_INDEX)
        self.db.commit()

    def build_graph(
        self,
        user_id: str,
        document_ids: List[str],
        depth: int = 2,
        project_id: Optional[str] = None,
        force: bool = False,
    ) -> GraphResponse:
        """Builds a knowledge graph scoped to the current user.

        When `project_id` is given, all of that project's documents are used;
        `document_ids` further narrows the selection. Both are always filtered
        by `user_id` so users can never read another user's content. The user's
        tracked concepts for the project bias which concepts survive pruning.

        The built graph is saved as a new checkpoint in `graph_history`. Unless
        `force` is set, the most recent checkpoint is reused whenever the
        project's chunks and tracked preferences are unchanged, so the graph
        only regenerates when new papers are indexed or the user asks for it.
        """
        doc_ids = self._documents_for_graph(user_id, project_id, document_ids)
        if not doc_ids:
            return GraphResponse(nodes=[], edges=[])

        chunks = self._chunks_for(doc_ids)
        preferences = self._tracked_preferences(user_id, project_id)
        key = _build_key(user_id, project_id, doc_ids, depth, preferences, chunks)
        if not force:
            cached = _BUILD_CACHE.get(key)
            if cached is not None:
                return cached

        fingerprint = _fingerprint(chunks)
        prefs_key = json.dumps(sorted(preferences))

        if not force:
            saved = self._load_latest_checkpoint(user_id, project_id)
            if (
                saved is not None
                and saved["fingerprint"] == fingerprint
                and saved["prefs_key"] == prefs_key
            ):
                response = GraphResponse(**json.loads(saved["graph_json"]))
                self._cache_put(key, response)
                return response

        nodes, edges = self.builder.build(chunks, preferences)
        nodes = layout_nodes(nodes, edges)
        response = GraphResponse(
            nodes=[GraphNode(**node) for node in nodes],
            edges=[GraphEdge(**edge) for edge in edges],
        )
        self._cache_put(key, response)
        self._save_checkpoint(user_id, project_id, response, fingerprint, prefs_key)
        return response

    def _cache_put(self, key, response) -> None:
        if len(_BUILD_CACHE) >= 32:
            _BUILD_CACHE.clear()
        _BUILD_CACHE[key] = response

    def _chunks_for(self, doc_ids: List[str]) -> List[dict]:
        placeholders = ",".join("?" * len(doc_ids))
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT id, document_id, content, embedded_at FROM chunks WHERE document_id IN ({placeholders})",
            doc_ids,
        )
        return [dict(row) for row in cursor.fetchall()]

    # --- checkpoints / history ------------------------------------------------

    def _save_checkpoint(
        self,
        user_id: str,
        project_id: Optional[str],
        response: GraphResponse,
        fingerprint: str,
        prefs_key: str,
    ) -> dict:
        checkpoint_id = generate_id()
        self.db.execute(
            """INSERT INTO graph_history (id, user_id, project_id, graph_json, fingerprint, prefs_key)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (checkpoint_id, user_id, project_id, response.model_dump_json(), fingerprint, prefs_key),
        )
        self.db.commit()
        row = self.db.execute(
            "SELECT * FROM graph_history WHERE id = ?", (checkpoint_id,)
        ).fetchone()
        return self._checkpoint_dict(row)

    def _load_latest_checkpoint(
        self,
        user_id: str,
        project_id: Optional[str],
    ) -> Optional[dict]:
        if not project_id:
            return None
        row = self.db.execute(
            """SELECT graph_json, fingerprint, prefs_key FROM graph_history
               WHERE user_id = ? AND project_id = ?
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (user_id, project_id),
        ).fetchone()
        if row is None:
            return None
        raw = json.loads(row["graph_json"])
        if any("x" not in n or "y" not in n for n in raw.get("nodes", [])):
            return None
        return {
            "graph_json": row["graph_json"],
            "fingerprint": row["fingerprint"],
            "prefs_key": row["prefs_key"],
        }

    def list_history(self, user_id: str, project_id: str) -> List[dict]:
        self._require_project(user_id, project_id)
        rows = self.db.execute(
            """SELECT * FROM graph_history
               WHERE user_id = ? AND project_id = ?
               ORDER BY created_at DESC, rowid DESC""",
            (user_id, project_id),
        ).fetchall()
        return [self._checkpoint_dict(row) for row in rows]

    def get_checkpoint(self, user_id: str, checkpoint_id: str) -> Optional[dict]:
        row = self.db.execute(
            "SELECT * FROM graph_history WHERE id = ? AND user_id = ?",
            (checkpoint_id, user_id),
        ).fetchone()
        if row is None:
            return None
        try:
            self.db.execute(
                """UPDATE graph_history
                   SET is_active = 0
                   WHERE user_id = ? AND project_id = ?""",
                (user_id, row["project_id"]),
            )
            self.db.execute(
                "UPDATE graph_history SET is_active = 1 WHERE id = ?",
                (checkpoint_id,),
            )
            self.db.commit()
            is_active = True
        except Exception:
            is_active = bool(row["is_active"]) if "is_active" in row.keys() else False
        data = self._checkpoint_dict(row)
        data["is_active"] = is_active
        data["graph"] = GraphResponse(**json.loads(row["graph_json"]))
        return data

    def delete_checkpoint(self, user_id: str, checkpoint_id: str) -> bool:
        cursor = self.db.execute(
            "DELETE FROM graph_history WHERE id = ? AND user_id = ?",
            (checkpoint_id, user_id),
        )
        self.db.commit()
        return cursor.rowcount > 0

    def set_favourite(
        self,
        user_id: str,
        checkpoint_id: str,
        is_favourite: bool,
    ) -> Optional[dict]:
        cursor = self.db.execute(
            "UPDATE graph_history SET is_favourite = ? WHERE id = ? AND user_id = ?",
            (1 if is_favourite else 0, checkpoint_id, user_id),
        )
        self.db.commit()
        if cursor.rowcount == 0:
            return None
        row = self.db.execute(
            "SELECT * FROM graph_history WHERE id = ? AND user_id = ?",
            (checkpoint_id, user_id),
        ).fetchone()
        return self._checkpoint_dict(row)

    @staticmethod
    def _checkpoint_dict(row) -> dict:
        raw = json.loads(row["graph_json"])
        try:
            is_active = bool(row["is_active"])
        except (IndexError, KeyError):
            is_active = False
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "fingerprint": row["fingerprint"],
            "prefs_key": row["prefs_key"],
            "is_favourite": bool(row["is_favourite"]),
            "is_active": is_active,
            "created_at": row["created_at"],
            "nodes": len(raw.get("nodes", [])),
            "edges": len(raw.get("edges", [])),
        }

    def _require_project(self, user_id: str, project_id: str) -> None:
        row = self.db.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
        if not row:
            raise ValueError("Project not found")

    def detect_themes(
        self,
        user_id: str,
        project_id: str,
        limit: int = 5,
    ) -> List[dict]:
        """Detects the top concepts per document as candidate themes.

        Concepts are re-extracted from each document's indexed chunks and
        aggregated by frequency. The per-document top-N give the user a curated
        set to track, instead of surfacing every extracted keyword.
        """
        doc_ids = self._documents_for_graph(user_id, project_id, [])
        if not doc_ids:
            return []

        placeholders = ",".join("?" * len(doc_ids))
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT id, title FROM documents WHERE id IN ({placeholders})",
            doc_ids,
        )
        titles = {row["id"]: row["title"] for row in cursor.fetchall()}

        cursor.execute(
            f"SELECT document_id, content FROM chunks WHERE document_id IN ({placeholders})",
            doc_ids,
        )
        by_doc: dict = defaultdict(Counter)
        for row in cursor.fetchall():
            concepts = self.builder.extractor.extract(row["content"])
            by_doc[row["document_id"]].update(concepts)

        return [
            {
                "doc_id": doc_id,
                "doc_name": titles.get(doc_id, "Untitled document"),
                "themes": [{"concept": c, "count": n} for c, n in counter.most_common(limit)],
            }
            for doc_id, counter in by_doc.items()
        ]

    def _tracked_preferences(self, user_id: str, project_id: Optional[str]) -> List[str]:
        if not project_id:
            return []
        rows = self.db.execute(
            "SELECT concept FROM tracked_concepts WHERE user_id = ? AND project_id = ?",
            (user_id, project_id),
        ).fetchall()
        return [row["concept"] for row in rows]

    def _documents_for_graph(
        self,
        user_id: str,
        project_id: Optional[str],
        document_ids: List[str],
    ) -> List[str]:
        cursor = self.db.cursor()
        conditions = ["user_id = ?"]
        params: List[str] = [user_id]

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if document_ids:
            placeholders = ",".join("?" * len(document_ids))
            conditions.append(f"id IN ({placeholders})")
            params.extend(document_ids)

        cursor.execute(
            f"SELECT id FROM documents WHERE {' AND '.join(conditions)}",
            params,
        )
        return [row["id"] for row in cursor.fetchall()]
