"""
Pytest configuration and fixtures for LectureForge tests.
"""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="session")
def test_env_vars():
    """Set up test environment variables."""
    os.environ["OPENAI_API_KEY"] = "sk-test-key-1234567890abcdefghijklmnopqrstuvwxyz"
    os.environ["SERPER_API_KEY"] = "test-serper-key-1234567890"
    os.environ["PEXELS_API_KEY"] = "test-pexels-key"
    os.environ["UNSPLASH_ACCESS_KEY"] = "test-unsplash-key"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_response = MagicMock()
    mock_response.content = "This is a test response from OpenAI."
    mock_response.usage = MagicMock(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150
    )
    return mock_response


@pytest.fixture
def mock_llm(mock_openai_response):
    """Mock LangChain LLM."""
    with patch("lecture_forge.agents.base.ChatOpenAI") as mock:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = mock_openai_response
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_pdf_path(temp_dir: Path) -> Path:
    """Create a sample PDF file for testing."""
    pdf_path = temp_dir / "sample.pdf"
    # Create a minimal PDF (not a real PDF, but good enough for some tests)
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n")
    return pdf_path


@pytest.fixture
def sample_text_content() -> str:
    """Sample text content for testing."""
    return """
# Machine Learning Basics

Machine learning is a subset of artificial intelligence that enables systems
to learn and improve from experience without being explicitly programmed.

## Types of Machine Learning

1. **Supervised Learning**: Learning from labeled data
2. **Unsupervised Learning**: Finding patterns in unlabeled data
3. **Reinforcement Learning**: Learning through trial and error

## Key Concepts

- **Training Data**: Data used to train the model
- **Test Data**: Data used to evaluate the model
- **Features**: Input variables
- **Labels**: Output variables (in supervised learning)
"""


@pytest.fixture
def sample_curriculum_data() -> dict:
    """Sample curriculum data for testing."""
    return {
        "topic": "Python Programming Basics",
        "duration_minutes": 120,
        "difficulty": "beginner",
        "target_audience": "Software engineering students",
        "learning_objectives": [
            "Understand Python syntax and basic data types",
            "Write simple Python programs",
            "Use control flow statements"
        ],
        "sections": [
            {
                "title": "Introduction to Python",
                "duration_minutes": 20,
                "content_type": "lecture",
                "key_points": ["What is Python?", "Why Python?", "Setting up environment"]
            },
            {
                "title": "Variables and Data Types",
                "duration_minutes": 30,
                "content_type": "lecture_with_examples",
                "key_points": ["Numbers", "Strings", "Lists", "Dictionaries"]
            },
            {
                "title": "Control Flow",
                "duration_minutes": 40,
                "content_type": "hands_on",
                "key_points": ["if statements", "for loops", "while loops"]
            }
        ]
    }


@pytest.fixture
def mock_vector_store():
    """Mock ChromaDB vector store."""
    mock_store = MagicMock()
    mock_store.query.return_value = {
        "documents": [["Sample document 1", "Sample document 2"]],
        "metadatas": [[{"source": "test.pdf", "page": 1}, {"source": "test.pdf", "page": 2}]],
        "distances": [[0.1, 0.2]]
    }
    return mock_store


@pytest.fixture
def mock_serper_response():
    """Mock Serper API response."""
    return {
        "searchParameters": {
            "q": "machine learning tutorial",
            "type": "search"
        },
        "organic": [
            {
                "title": "Machine Learning Tutorial",
                "link": "https://example.com/ml-tutorial",
                "snippet": "Learn machine learning basics..."
            },
            {
                "title": "ML Guide",
                "link": "https://example.com/ml-guide",
                "snippet": "Comprehensive guide to ML..."
            }
        ]
    }


@pytest.fixture(autouse=True)
def reset_config():
    """Reset configuration after each test."""
    yield
    # Cleanup after test if needed


@pytest.fixture
def sample_images() -> list:
    """Sample image metadata for testing."""
    return [
        {
            "id": "test_img_1",
            "url": "https://example.com/image1.jpg",
            "description": "A sample image",
            "width": 1920,
            "height": 1080,
            "source": "test",
            "query": "machine learning"
        },
        {
            "id": "test_img_2",
            "url": "https://example.com/image2.jpg",
            "description": "Another sample image",
            "width": 1280,
            "height": 720,
            "source": "test",
            "query": "python programming"
        }
    ]
