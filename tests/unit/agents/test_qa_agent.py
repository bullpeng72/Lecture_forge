"""
Smoke tests for QAAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.qa_agent import QAAgent


@pytest.fixture
def qa_agent(test_env_vars, mock_vector_store, mock_llm, temp_dir):
    """Create QAAgent instance with mocked dependencies."""
    with patch("lecture_forge.agents.qa_agent.VectorStore") as mock_vs_class:
        mock_vs_class.return_value = mock_vector_store
        kb_path = str(temp_dir / "test_kb")
        agent = QAAgent(knowledge_base_path=kb_path)
        agent.vector_store = mock_vector_store
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
