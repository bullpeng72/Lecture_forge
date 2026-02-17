"""
Unit tests for QA Agent quality improvements.
"""

import pytest

from lecture_forge.agents.qa_agent import QAAgent


class TestQAAgentQuality:
    """Test quality improvement features in QA Agent."""

    def test_calculate_confidence_high(self):
        """Test confidence calculation for high-quality results."""
        # Create agent instance with minimal setup
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "test_kb"
            kb_path.mkdir()

            # This will fail to load KB but that's OK for testing confidence calc
            try:
                agent = QAAgent(str(kb_path))
            except Exception:
                # If KB loading fails, create a minimal agent for testing
                agent = object.__new__(QAAgent)
                agent.knowledge_base_path = kb_path

        # High-quality results: 12 entries → result_factor = 1.0
        merged_results = [
            {"score": 0.9, "document": "test", "metadata": {}},
            {"score": 0.88, "document": "test", "metadata": {}},
            {"score": 0.85, "document": "test", "metadata": {}},
            {"score": 0.82, "document": "test", "metadata": {}},
            {"score": 0.80, "document": "test", "metadata": {}},
            {"score": 0.78, "document": "test", "metadata": {}},
            {"score": 0.75, "document": "test", "metadata": {}},
            {"score": 0.72, "document": "test", "metadata": {}},
            {"score": 0.70, "document": "test", "metadata": {}},
            {"score": 0.68, "document": "test", "metadata": {}},
            {"score": 0.65, "document": "test", "metadata": {}},
            {"score": 0.62, "document": "test", "metadata": {}},
        ]

        # > 400 chars → length_factor = 1.0
        # confidence = top_score(0.9) × result_factor(1.0) × length_factor(1.0) = 0.9
        answer = (
            "This is a comprehensive and detailed answer explaining the topic with "
            "sufficient depth and nuance. It covers multiple aspects, provides context, "
            "and explains the relationships between concepts clearly and thoroughly. "
            "Furthermore, the answer delves into additional subtleties, providing examples "
            "drawn from the available context to ensure the reader gains a complete "
            "understanding of the subject matter being discussed in detail."
        )

        confidence = agent._calculate_confidence(merged_results, answer)

        # confidence = 0.9 × 1.0 × 1.0 × 1.0 = 0.9
        assert confidence > 0.8
        assert confidence <= 1.0

    def test_calculate_confidence_low(self):
        """Test confidence calculation for low-quality results."""
        agent = QAAgent.__new__(QAAgent)

        # Low-quality results
        merged_results = [
            {"score": 0.4, "document": "test", "metadata": {}},
            {"score": 0.3, "document": "test", "metadata": {}},
        ]

        answer = "Short answer."

        confidence = agent._calculate_confidence(merged_results, answer)

        # Should be low confidence (< 0.5)
        assert confidence < 0.5
        assert confidence >= 0.0

    def test_calculate_confidence_uncertain_answer(self):
        """Test confidence with uncertain answer."""
        agent = QAAgent.__new__(QAAgent)

        merged_results = [
            {"score": 0.8, "document": "test", "metadata": {}},
        ]

        answer = "I'm not sure about this. The context doesn't provide clear information."

        confidence = agent._calculate_confidence(merged_results, answer)

        # Should be reduced due to uncertainty
        assert confidence < 0.7

    def test_diversity_selection(self):
        """Test diversity-aware result selection."""
        agent = QAAgent.__new__(QAAgent)

        # Results from same source-page
        ranked_results = [
            {
                "score": 0.9,
                "document": "chunk1",
                "metadata": {"source": "doc.pdf", "page_number": 1},
            },
            {
                "score": 0.88,
                "document": "chunk2",
                "metadata": {"source": "doc.pdf", "page_number": 1},
            },
            {
                "score": 0.86,
                "document": "chunk3",
                "metadata": {"source": "doc.pdf", "page_number": 1},
            },
            {
                "score": 0.84,
                "document": "chunk4",
                "metadata": {"source": "doc.pdf", "page_number": 2},
            },
        ]

        selected = agent._diversity_selection(ranked_results, top_k=3)

        # Should select max 3 from same source-page
        assert len(selected) == 3

        # Check diversity
        page_1_count = sum(1 for r in selected if r["metadata"]["page_number"] == 1)
        assert page_1_count <= 3

    def test_diversity_selection_different_sources(self):
        """Test diversity selection with different sources."""
        agent = QAAgent.__new__(QAAgent)

        ranked_results = [
            {"score": 0.9, "document": "c1", "metadata": {"source": "doc1.pdf", "page_number": 1}},
            {"score": 0.85, "document": "c2", "metadata": {"source": "doc2.pdf", "page_number": 1}},
            {"score": 0.8, "document": "c3", "metadata": {"source": "doc3.pdf", "page_number": 1}},
            {"score": 0.75, "document": "c4", "metadata": {"source": "doc1.pdf", "page_number": 2}},
        ]

        selected = agent._diversity_selection(ranked_results, top_k=3)

        assert len(selected) == 3

        # Should prefer different sources
        sources = [r["metadata"]["source"] for r in selected]
        assert len(set(sources)) >= 2  # At least 2 different sources

    def test_diversity_selection_insufficient_results(self):
        """Test diversity selection when results < top_k."""
        agent = QAAgent.__new__(QAAgent)

        ranked_results = [
            {"score": 0.9, "document": "c1", "metadata": {"source": "doc.pdf", "page_number": 1}},
            {"score": 0.8, "document": "c2", "metadata": {"source": "doc.pdf", "page_number": 1}},
        ]

        selected = agent._diversity_selection(ranked_results, top_k=5)

        # Should return all available results
        assert len(selected) == 2
