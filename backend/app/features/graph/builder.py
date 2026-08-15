from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from app.features.graph.concept_extractor import ConceptExtractor


class GraphBuilder:
    """Builds a concept co-occurrence graph from document chunks.

    Nodes are concepts extracted from chunk text, weighted by the number of
    chunks they appear in. Edges connect concepts that co-occur in the same
    chunk, weighted by how many chunks share both concepts.
    """

    def __init__(
        self,
        max_concepts_per_chunk: int = 8,
        max_nodes: int = 60,
        max_edges: int = 250,
    ):
        self.extractor = ConceptExtractor(max_concepts=max_concepts_per_chunk)
        self.max_nodes = max_nodes
        self.max_edges = max_edges

    def build(self, chunks: List[dict]) -> Tuple[List[dict], List[dict]]:
        concept_chunks: Dict[str, set] = defaultdict(set)
        pair_counts: Counter = Counter()

        for chunk in chunks:
            chunk_id = chunk.get("id", "")
            concepts = self.extractor.extract(chunk.get("content", ""))
            for concept in concepts:
                concept_chunks[concept].add(chunk_id)
            for i in range(len(concepts)):
                for j in range(i + 1, len(concepts)):
                    a, b = concepts[i], concepts[j]
                    key = (a, b) if a <= b else (b, a)
                    pair_counts[key] += 1

        node_rows = [
            {"label": label, "weight": len(chunk_ids)}
            for label, chunk_ids in concept_chunks.items()
        ]
        node_rows.sort(key=lambda r: (-r["weight"], r["label"]))
        node_rows = node_rows[: self.max_nodes]

        kept = {r["label"] for r in node_rows}
        edge_rows = [
            {"source": a, "target": b, "weight": count}
            for (a, b), count in pair_counts.items()
            if a in kept and b in kept
        ]
        edge_rows.sort(key=lambda r: (-r["weight"], r["source"], r["target"]))
        edge_rows = edge_rows[: self.max_edges]

        nodes = [
            {"id": f"concept:{label}", "label": label, "type": "concept", "weight": weight}
            for label, weight in ((r["label"], r["weight"]) for r in node_rows)
        ]
        edges = [
            {
                "source": f"concept:{e['source']}",
                "target": f"concept:{e['target']}",
                "weight": e["weight"],
            }
            for e in edge_rows
        ]
        return nodes, edges
