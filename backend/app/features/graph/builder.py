import math
import random
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional, Tuple

from app.features.graph.concept_extractor import ConceptExtractor


def layout_nodes(
    nodes: List[dict],
    edges: List[dict],
    width: float = 800,
    height: float = 600,
    iterations: int = 140,
) -> List[dict]:
    """Runs a force-directed layout and returns nodes with ``x``/``y`` set.

    The physics mirror the layout the frontend used to run, so the browser can
    render positions straight from the payload instead of re-simulating. The
    result is deterministic only modulo Python's random seed; a regenerated
    graph simply gets a fresh but sensible arrangement.
    """
    ids = [n["id"] for n in nodes]
    positions = {
        nid: [width / 2 + (random.random() - 0.5) * 140, height / 2 + (random.random() - 0.5) * 140]
        for nid in ids
    }
    velocities = {nid: [0.0, 0.0] for nid in ids}
    pairs = [(i, j) for i in range(len(ids)) for j in range(i + 1, len(ids))]
    springs = [
        (e["source"], e["target"])
        for e in edges
        if e.get("source") in positions and e.get("target") in positions
    ]

    repulsion = 4200.0
    rest_length = 120.0

    for it in range(iterations):
        temperature = 1.0 - it / iterations
        for a, b in pairs:
            pa, pb = positions[ids[a]], positions[ids[b]]
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            d2 = dx * dx + dy * dy
            if d2 < 1:
                dx, dy = random.random() - 0.5, random.random() - 0.5
                d2 = dx * dx + dy * dy
            d = math.sqrt(d2)
            force = repulsion / d2
            va, vb = velocities[ids[a]], velocities[ids[b]]
            va[0] -= (dx / d) * force
            va[1] -= (dy / d) * force
            vb[0] += (dx / d) * force
            vb[1] += (dy / d) * force

        for s, t in springs:
            ps, pt = positions[s], positions[t]
            dx, dy = pt[0] - ps[0], pt[1] - ps[1]
            d = math.sqrt(dx * dx + dy * dy) or 1
            force = (d - rest_length) * 0.02
            vs, vt = velocities[s], velocities[t]
            vs[0] += (dx / d) * force
            vs[1] += (dy / d) * force
            vt[0] -= (dx / d) * force
            vt[1] -= (dy / d) * force

        for nid in ids:
            p, v = positions[nid], velocities[nid]
            v[0] += (width / 2 - p[0]) * 0.01
            v[1] += (height / 2 - p[1]) * 0.01
            v[0] *= 0.85
            v[1] *= 0.85
            p[0] += v[0] * temperature
            p[1] += v[1] * temperature
            p[0] = min(width - 40, max(40, p[0]))
            p[1] = min(height - 40, max(40, p[1]))

    return [
        {**n, "x": round(positions[n["id"]][0], 2), "y": round(positions[n["id"]][1], 2)}
        for n in nodes
    ]


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

    def build(
        self,
        chunks: List[dict],
        preferences: Optional[List[str]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[List[dict], List[dict]]:
        """Builds a concept graph, biasing toward `preferences`.

        Concepts matching a tracked preference (exact, or substring both ways
        for phrases of length >= 3) are never pruned by the node cap and their
        edges are ranked first, so the graph reflects the user's tracked themes.

        `on_progress(done, total)` is invoked after each chunk is processed so
        background generation can surface a progress percentage.
        """
        prefs = self._normalize_preferences(preferences)

        concept_chunks: Dict[str, set] = defaultdict(set)
        pair_counts: Counter = Counter()

        total = len(chunks)
        for idx, chunk in enumerate(chunks):
            if on_progress:
                on_progress(idx + 1, total)
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
        node_rows = self._apply_preferences(node_rows, prefs)

        kept = {r["label"] for r in node_rows}
        edge_rows = [
            {"source": a, "target": b, "weight": count}
            for (a, b), count in pair_counts.items()
            if a in kept and b in kept
        ]
        if prefs:
            edge_rows.sort(
                key=lambda r: (
                    0 if self._matches_pref(r["source"], prefs) or self._matches_pref(r["target"], prefs) else 1,
                    -r["weight"],
                    r["source"],
                    r["target"],
                )
            )
        else:
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

    @staticmethod
    def _normalize_preferences(preferences: Optional[List[str]]) -> List[str]:
        if not preferences:
            return []
        seen: set = set()
        normalized: List[str] = []
        for pref in preferences:
            pref = (pref or "").strip().lower()
            if len(pref) < 2 or pref in seen:
                continue
            seen.add(pref)
            normalized.append(pref)
        return normalized

    @staticmethod
    def _matches_pref(label: str, prefs: List[str]) -> bool:
        label = label.lower()
        return any(
            label == pref or (len(pref) >= 3 and (pref in label or label in pref))
            for pref in prefs
        )

    def _apply_preferences(self, node_rows: List[dict], prefs: List[str]) -> List[dict]:
        if not prefs:
            return node_rows[: self.max_nodes]
        preferred = [r for r in node_rows if self._matches_pref(r["label"], prefs)]
        others = [r for r in node_rows if not self._matches_pref(r["label"], prefs)]
        combined = preferred[: self.max_nodes] + others[: max(0, self.max_nodes - len(preferred))]
        return combined
