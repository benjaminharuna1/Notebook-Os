from app.features.graph.builder import GraphBuilder
from app.features.graph.concept_extractor import ConceptExtractor


class TestConceptExtractor:
    def test_extracts_capitalized_phrases(self):
        text = "The AI Team met with John Smith about the Quantum Computing roadmap."
        concepts = ConceptExtractor().extract(text)
        assert "John Smith" in concepts
        assert "Quantum Computing" in concepts

    def test_filters_stopword_phrases_and_words(self):
        text = "The and of it. The and of it. The and of it."
        assert ConceptExtractor().extract(text) == []

    def test_limits_concept_count(self):
        text = " ".join(f"Concept{i} discussion" for i in range(20))
        concepts = ConceptExtractor(max_concepts=5).extract(text)
        assert len(concepts) <= 5

    def test_empty_text(self):
        assert ConceptExtractor().extract("") == []


class TestGraphBuilder:
    def _chunks(self):
        return [
            {"id": "c1", "document_id": "d1", "content": "Neural Networks and Deep Learning converge."},
            {"id": "c2", "document_id": "d1", "content": "Deep Learning powers Neural Networks today."},
            {"id": "c3", "document_id": "d2", "content": "Database indexing improves Query Performance."},
        ]

    def test_builds_nodes_and_edges(self):
        nodes, edges = GraphBuilder().build(self._chunks())
        labels = {n["label"] for n in nodes}
        assert "Neural Networks" in labels
        assert any(e["weight"] >= 2 for e in edges)

    def test_co_occurrence_weighted_by_shared_chunks(self):
        nodes, edges = GraphBuilder().build(self._chunks())
        by_key = {(e["source"], e["target"]): e["weight"] for e in edges}
        pair = None
        for src, tgt in by_key:
            if "Neural" in src and "Deep" in tgt or "Deep" in src and "Neural" in tgt:
                pair = (src, tgt)
        assert pair is not None
        assert by_key[pair] == 2

    def test_empty_chunks(self):
        nodes, edges = GraphBuilder().build([])
        assert nodes == []
        assert edges == []

    def test_respects_caps(self):
        chunks = [
            {"id": f"c{i}", "document_id": "d", "content": f"n{'a' * (i + 3)} apple"}
            for i in range(60)
        ]
        nodes, edges = GraphBuilder(max_nodes=10, max_edges=50).build(chunks)
        assert len(nodes) == 10
        assert len(edges) <= 50
        node_ids = {n["id"] for n in nodes}
        for edge in edges:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids
