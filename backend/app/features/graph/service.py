from typing import List, Optional

from app.features.graph.builder import GraphBuilder
from app.features.graph.schemas import GraphEdge, GraphNode, GraphResponse


class GraphService:
    def __init__(self, db):
        self.db = db
        self.builder = GraphBuilder()

    def build_graph(
        self,
        user_id: str,
        document_ids: List[str],
        depth: int = 2,
        project_id: Optional[str] = None,
    ) -> GraphResponse:
        """Builds a knowledge graph scoped to the current user.

        When `project_id` is given, all of that project's documents are used;
        `document_ids` further narrows the selection. Both are always filtered
        by `user_id` so users can never read another user's content.
        """
        doc_ids = self._documents_for_graph(user_id, project_id, document_ids)
        if not doc_ids:
            return GraphResponse(nodes=[], edges=[])

        placeholders = ",".join("?" * len(doc_ids))
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT id, document_id, content FROM chunks WHERE document_id IN ({placeholders})",
            doc_ids,
        )
        chunks = [dict(row) for row in cursor.fetchall()]

        nodes, edges = self.builder.build(chunks)
        return GraphResponse(
            nodes=[GraphNode(**node) for node in nodes],
            edges=[GraphEdge(**edge) for edge in edges],
        )

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
