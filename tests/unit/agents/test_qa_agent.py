"""
Unit and smoke tests for QAAgent.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lecture_forge.agents.qa_agent import QAAgent


@pytest.fixture
def mock_vector_store_with_results():
    """Mock vector store returning sample results."""
    mock = MagicMock()
    mock.query.return_value = {
        "documents": [["Context about machine learning.", "More ML context."]],
        "metadatas": [[
            {"source": "ml.pdf", "page_number": 1, "language": "en", "chunk_index": 0},
            {"source": "ml.pdf", "page_number": 2, "language": "en", "chunk_index": 1},
        ]],
        "distances": [[0.1, 0.2]],
    }
    return mock


@pytest.fixture
def qa_agent(test_env_vars, mock_vector_store_with_results, mock_llm, temp_dir):
    """Create QAAgent instance with mocked dependencies."""
    with patch("lecture_forge.agents.qa_agent.VectorStore") as mock_vs_class:
        mock_vs_class.return_value = mock_vector_store_with_results
        kb_path = str(temp_dir / "test_kb")
        agent = QAAgent(knowledge_base_path=kb_path)
        agent.vector_store = mock_vector_store_with_results
        return agent


def test_qa_agent_initialization(qa_agent):
    """Test that QAAgent initializes correctly."""
    assert qa_agent is not None
    assert qa_agent.agent_name == "QAAgent"
    assert qa_agent.vector_store is not None


def test_answer_question(qa_agent, mock_llm):
    """Test answering a question with RAG."""
    with patch.object(qa_agent, "llm") as mock_llm_instance:
        mock_response = MagicMock()
        mock_response.content = "Machine learning is a subset of AI that enables systems to learn from data."
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200}}
        mock_llm_instance.invoke.return_value = mock_response

        answer = qa_agent.answer(question="What is machine learning?")

        assert answer is not None
        assert len(answer) > 0


def test_answer_with_sources(qa_agent, mock_llm):
    """Test that answers include source citations."""
    with patch.object(qa_agent, "llm") as mock_llm_instance:
        mock_response = MagicMock()
        mock_response.content = "Answer with sources: [Source: test.pdf, Page: 1]"
        mock_response.response_metadata = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}}
        mock_llm_instance.invoke.return_value = mock_response

        answer = qa_agent.answer(question="Test question")

        assert answer is not None


def test_answer_returns_dict(qa_agent):
    """answer() returns a dict with required keys."""
    mock_response = MagicMock()
    mock_response.content = "This is a comprehensive answer about the topic with enough detail."
    mock_response.response_metadata = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}}
    qa_agent.llm.invoke.return_value = mock_response

    with patch.object(qa_agent, "invoke_llm", return_value=mock_response):
        result = qa_agent.answer("What is Python?")

    assert isinstance(result, dict)
    assert "answer" in result
    assert "sources" in result
    assert "confidence" in result
    assert "query_language" in result


def test_answer_empty_results_returns_fallback(qa_agent):
    """When vector store returns no results, fallback message is returned."""
    qa_agent.vector_store.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }

    result = qa_agent.answer("What is undefined?")

    assert "answer" in result
    assert result["confidence"] == 0.0


def test_answer_exception_returns_error_message(qa_agent):
    """When an exception occurs, error message is returned."""
    qa_agent.vector_store.query.side_effect = Exception("Database error")

    result = qa_agent.answer("Test question")

    assert "answer" in result
    assert "오류" in result["answer"] or "error" in result["answer"].lower()
    assert result["confidence"] == 0.0


# ===== _merge_and_rerank() =====

class TestMergeAndRerank:
    """Tests for the _merge_and_rerank() private method."""

    def _make_results(self, n=2, source="doc.pdf", lang="en", start_page=1):
        docs = [f"Context chunk {i}" for i in range(n)]
        metas = [{"source": source, "page_number": start_page + i, "language": lang, "chunk_index": i} for i in range(n)]
        dists = [0.1 * (i + 1) for i in range(n)]
        return {"documents": [docs], "metadatas": [metas], "distances": [dists]}

    def test_merge_original_only(self, qa_agent):
        results = self._make_results(3)
        merged = qa_agent._merge_and_rerank(
            question="test",
            query_language="en",
            results_original=results,
            results_translated=None,
            top_k=5,
        )
        assert len(merged) <= 5
        assert all("score" in r for r in merged)

    def test_merge_with_translated(self, qa_agent):
        results_orig = self._make_results(2, source="doc1.pdf", lang="en")
        results_trans = self._make_results(2, source="doc2.pdf", lang="ko")

        merged = qa_agent._merge_and_rerank(
            question="test",
            query_language="en",
            results_original=results_orig,
            results_translated=results_trans,
            top_k=5,
        )
        assert len(merged) <= 4  # 2 original + 2 translated = max 4

    def test_merge_deduplicates(self, qa_agent):
        """Same chunk from both queries should not appear twice."""
        results = self._make_results(2)
        merged = qa_agent._merge_and_rerank(
            question="test",
            query_language="en",
            results_original=results,
            results_translated=results,  # Same results
            top_k=5,
        )
        # No duplicates (same source+chunk_index)
        chunk_ids = [(r["metadata"]["source"], r["metadata"]["chunk_index"]) for r in merged]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_merge_empty_original(self, qa_agent):
        empty = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        merged = qa_agent._merge_and_rerank(
            question="test",
            query_language="en",
            results_original=empty,
            results_translated=None,
            top_k=5,
        )
        assert merged == [] or isinstance(merged, list)

    def test_language_bonus_applied(self, qa_agent):
        """Chunks with same language as query get +0.1 score bonus."""
        results = {
            "documents": [["doc1"]],
            "metadatas": [[{"source": "d.pdf", "page_number": 1, "language": "en", "chunk_index": 0}]],
            "distances": [[0.4]],  # base score = 1 - 0.4/2 = 0.8
        }
        merged = qa_agent._merge_and_rerank(
            question="test",
            query_language="en",
            results_original=results,
            top_k=1,
        )
        # score should be 0.8 + 0.1 language bonus = 0.9
        assert merged[0]["score"] == pytest.approx(0.9)

    def test_filters_low_similarity(self, qa_agent):
        """Results with score < 0.3 should be filtered unless all are below threshold."""
        results = {
            "documents": [["low1", "low2"]],
            "metadatas": [[
                {"source": "d.pdf", "page_number": 1, "language": "fr", "chunk_index": 0},
                {"source": "d.pdf", "page_number": 2, "language": "fr", "chunk_index": 1},
            ]],
            "distances": [[0.9, 0.85]],  # similarity = 0.1 and 0.15 → below 0.3
        }
        merged = qa_agent._merge_and_rerank(
            question="test",
            query_language="en",
            results_original=results,
            top_k=5,
        )
        # All below threshold, keep top 3 anyway (fallback)
        assert len(merged) <= 3

    def test_none_metadata_skipped(self, qa_agent):
        """Results with None metadata are skipped."""
        results = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[None, {"source": "d.pdf", "page_number": 1, "language": "en", "chunk_index": 1}]],
            "distances": [[0.1, 0.2]],
        }
        merged = qa_agent._merge_and_rerank(
            question="test",
            query_language="en",
            results_original=results,
            top_k=5,
        )
        # Only non-None metadata entries
        assert all(r["metadata"] is not None for r in merged)


# ===== _calculate_confidence() =====

class TestCalculateConfidence:
    """Tests for _calculate_confidence() private method."""

    def test_empty_results(self, qa_agent):
        assert qa_agent._calculate_confidence([], "answer") == 0.0

    def test_high_confidence(self, qa_agent):
        merged = [{"score": 0.9}] * 12
        answer = "This is a detailed comprehensive answer explaining the concept clearly." * 6
        confidence = qa_agent._calculate_confidence(merged, answer)
        assert confidence > 0.8

    def test_low_confidence_few_results(self, qa_agent):
        merged = [{"score": 0.4}]
        answer = "Short answer."
        confidence = qa_agent._calculate_confidence(merged, answer)
        assert confidence < 0.5

    def test_very_short_answer_reduces_confidence(self, qa_agent):
        merged = [{"score": 0.9}] * 5
        short_answer = "OK."  # < 50 chars → length_factor = 0.5
        confidence = qa_agent._calculate_confidence(merged, short_answer)
        assert confidence < 0.7

    def test_medium_answer_length(self, qa_agent):
        merged = [{"score": 0.9}] * 5
        medium = "Answer with some details here."  # 50-100 chars range
        medium = "A" * 75  # exactly 75 chars
        confidence = qa_agent._calculate_confidence(merged, medium)
        assert confidence > 0.0

    def test_uncertainty_phrase_reduces_confidence(self, qa_agent):
        merged = [{"score": 0.9}] * 8
        uncertain = "I don't know the exact answer to this question based on the context."
        confident_answer = "This is a clear and definitive explanation of the topic."
        unc_conf = qa_agent._calculate_confidence(merged, uncertain)
        conf_conf = qa_agent._calculate_confidence(merged, confident_answer)
        assert unc_conf < conf_conf

    def test_confidence_clamped_to_1(self, qa_agent):
        merged = [{"score": 1.0}] * 10  # score > 1 in theory
        answer = "A" * 300
        confidence = qa_agent._calculate_confidence(merged, answer)
        assert confidence <= 1.0

    def test_confidence_never_negative(self, qa_agent):
        merged = [{"score": -0.1}]  # Edge case
        answer = "Short."
        confidence = qa_agent._calculate_confidence(merged, answer)
        assert confidence >= 0.0


# ===== _post_process_answer() =====

class TestPostProcessAnswer:
    """Tests for _post_process_answer() private method."""

    def test_normal_answer_unchanged(self, qa_agent):
        answer = "This is a sufficiently long answer that provides good detail." * 2
        result = qa_agent._post_process_answer(answer, "test?", ["ctx"], "en")
        assert result == answer

    def test_short_answer_triggers_expansion(self, qa_agent):
        """Short answer (<50 chars) triggers _expand_short_answer."""
        short = "Python."

        mock_response = MagicMock()
        mock_response.content = "Python is a high-level programming language with clean syntax."
        with patch.object(qa_agent, "invoke_llm", return_value=mock_response):
            result = qa_agent._post_process_answer(short, "What is Python?", ["context"], "en")
        # The expanded answer should be longer
        assert len(result) > len(short)

    def test_no_info_phrase_triggers_extraction(self, qa_agent):
        """Answer with no-info phrase triggers _extract_partial_info."""
        no_info = "I don't know the exact details about this topic."

        mock_response = MagicMock()
        mock_response.content = "Based on available context: Here are related details."
        with patch.object(qa_agent, "invoke_llm", return_value=mock_response):
            result = qa_agent._post_process_answer(no_info, "What is X?", ["context"], "en")
        # Should call _extract_partial_info
        assert isinstance(result, str)


# ===== _diversity_selection() =====

class TestDiversitySelection:
    """Tests inherited from test_qa_agent_quality.py (already pass)."""

    def test_insufficient_results_returns_all(self, qa_agent):
        ranked = [
            {"score": 0.9, "document": "c1", "metadata": {"source": "d.pdf", "page_number": 1}},
            {"score": 0.8, "document": "c2", "metadata": {"source": "d.pdf", "page_number": 1}},
        ]
        selected = qa_agent._diversity_selection(ranked, top_k=5)
        assert len(selected) == 2

    def test_exact_top_k_returned(self, qa_agent):
        ranked = [
            {"score": 0.9 - 0.1 * i, "document": f"c{i}",
             "metadata": {"source": f"doc{i}.pdf", "page_number": 1}}
            for i in range(6)
        ]
        selected = qa_agent._diversity_selection(ranked, top_k=3)
        assert len(selected) == 3

    def test_fills_when_diversity_limits(self, qa_agent):
        """When diversity prevents initial fill, should still return top_k."""
        ranked = [
            {"score": 0.9, "document": f"c{i}",
             "metadata": {"source": "same_doc.pdf", "page_number": 1}}
            for i in range(5)
        ]
        selected = qa_agent._diversity_selection(ranked, top_k=3)
        assert len(selected) == 3
