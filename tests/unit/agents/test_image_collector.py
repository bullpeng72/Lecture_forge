"""
Smoke tests for ImageCollectorAgent.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.image_collector import ImageCollectorAgent


@pytest.fixture
def image_collector(test_env_vars, mock_vector_store):
    """Create ImageCollectorAgent instance with mocked dependencies."""
    agent = ImageCollectorAgent(session_id="test_session", vector_store=mock_vector_store)
    return agent


def test_image_collector_initialization(image_collector):
    """Test that ImageCollectorAgent initializes correctly."""
    assert image_collector is not None
    assert image_collector.agent_name == "ImageCollectorAgent"
    assert image_collector.session_id == "test_session"


def test_collect_from_pdfs(image_collector, sample_pdf_path):
    """Test image collection from PDFs."""
    with patch.object(image_collector.pdf_extractor, "run") as mock_extract:
        mock_extract.return_value = {
            "success": True,
            "images": [
                {
                    "id": "test_img_1",
                    "path": "/tmp/test_img_1.png",
                    "hash": "abcd1234",
                    "width": 800,
                    "height": 600,
                }
            ],
            "error": None,
        }

        result = image_collector.collect(
            sources={"pdfs": [str(sample_pdf_path)], "urls": [], "image_keywords": []},
            download_search_images=False,
        )

        assert result is not None


def test_collect_with_empty_sources(image_collector):
    """Test collection with no sources."""
    result = image_collector.collect(
        sources={"pdfs": [], "urls": [], "image_keywords": []},
        download_search_images=False,
    )

    assert result is not None
    assert "images" in result or "all_images" in result
