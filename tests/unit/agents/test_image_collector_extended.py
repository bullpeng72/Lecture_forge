"""
Extended unit tests for ImageCollectorAgent - _build_image_page_map and get_images_by_keyword.
"""

from unittest.mock import MagicMock, patch

import pytest

from lecture_forge.agents.image_collector import ImageCollectorAgent


@pytest.fixture
def image_collector(test_env_vars, mock_vector_store):
    """Create ImageCollectorAgent instance."""
    agent = ImageCollectorAgent(session_id="test_session", vector_store=mock_vector_store)
    return agent


# ===== _build_image_page_map() =====

class TestBuildImagePageMap:
    def test_empty_input_returns_empty_dict(self, image_collector):
        result = image_collector._build_image_page_map([])
        assert result == {}

    def test_single_image(self, image_collector):
        pdf_images = [
            {"id": "img_1", "source": "doc.pdf", "page": 1,
             "path": "/img/1.png", "hash": "abc", "description": "desc",
             "alt_text": "alt", "width": 800, "height": 600}
        ]
        result = image_collector._build_image_page_map(pdf_images)
        assert "doc.pdf" in result
        assert 1 in result["doc.pdf"]
        assert len(result["doc.pdf"][1]) == 1
        assert result["doc.pdf"][1][0]["id"] == "img_1"

    def test_multiple_images_same_page(self, image_collector):
        pdf_images = [
            {"id": "img_1", "source": "doc.pdf", "page": 1,
             "path": "/img/1.png", "hash": "abc", "description": "", "alt_text": "", "width": 100, "height": 100},
            {"id": "img_2", "source": "doc.pdf", "page": 1,
             "path": "/img/2.png", "hash": "def", "description": "", "alt_text": "", "width": 100, "height": 100},
        ]
        result = image_collector._build_image_page_map(pdf_images)
        assert len(result["doc.pdf"][1]) == 2

    def test_multiple_pages(self, image_collector):
        pdf_images = [
            {"id": "img_1", "source": "doc.pdf", "page": 1,
             "path": "", "hash": "", "description": "", "alt_text": "", "width": None, "height": None},
            {"id": "img_2", "source": "doc.pdf", "page": 2,
             "path": "", "hash": "", "description": "", "alt_text": "", "width": None, "height": None},
        ]
        result = image_collector._build_image_page_map(pdf_images)
        assert 1 in result["doc.pdf"]
        assert 2 in result["doc.pdf"]

    def test_multiple_sources(self, image_collector):
        pdf_images = [
            {"id": "img_1", "source": "a.pdf", "page": 1,
             "path": "", "hash": "", "description": "", "alt_text": "", "width": None, "height": None},
            {"id": "img_2", "source": "b.pdf", "page": 1,
             "path": "", "hash": "", "description": "", "alt_text": "", "width": None, "height": None},
        ]
        result = image_collector._build_image_page_map(pdf_images)
        assert "a.pdf" in result
        assert "b.pdf" in result

    def test_skips_images_without_source(self, image_collector):
        pdf_images = [
            {"id": "img_1", "source": "", "page": 1, "path": "", "hash": "", "description": "", "alt_text": "", "width": None, "height": None},
        ]
        result = image_collector._build_image_page_map(pdf_images)
        assert result == {}

    def test_skips_images_without_page(self, image_collector):
        pdf_images = [
            {"id": "img_1", "source": "doc.pdf", "page": None, "path": "", "hash": "", "description": "", "alt_text": "", "width": None, "height": None},
        ]
        result = image_collector._build_image_page_map(pdf_images)
        assert result == {}

    def test_stored_keys_in_image_info(self, image_collector):
        pdf_images = [
            {"id": "img_1", "source": "doc.pdf", "page": 1,
             "path": "/img/1.png", "hash": "abc123", "description": "A diagram",
             "alt_text": "diagram alt", "width": 800, "height": 600}
        ]
        result = image_collector._build_image_page_map(pdf_images)
        img_info = result["doc.pdf"][1][0]
        assert img_info["id"] == "img_1"
        assert img_info["path"] == "/img/1.png"
        assert img_info["hash"] == "abc123"
        assert img_info["description"] == "A diagram"
        assert img_info["alt_text"] == "diagram alt"
        assert img_info["width"] == 800
        assert img_info["height"] == 600


# ===== get_images_by_keyword() =====

class TestGetImagesByKeyword:
    def _make_img(self, id, description="", alt_text="", query=""):
        return {"id": id, "description": description, "alt_text": alt_text, "query": query}

    def test_returns_empty_when_no_images(self, image_collector):
        image_collector.all_images = []
        result = image_collector.get_images_by_keyword("test")
        assert result == []

    def test_finds_by_description(self, image_collector):
        image_collector.all_images = [
            self._make_img("1", description="machine learning diagram"),
            self._make_img("2", description="other topic"),
        ]
        result = image_collector.get_images_by_keyword("machine learning")
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_finds_by_alt_text(self, image_collector):
        image_collector.all_images = [
            self._make_img("1", alt_text="neural network chart"),
        ]
        result = image_collector.get_images_by_keyword("neural network")
        assert len(result) == 1

    def test_finds_by_query(self, image_collector):
        image_collector.all_images = [
            self._make_img("1", query="deep learning"),
        ]
        result = image_collector.get_images_by_keyword("deep learning")
        assert len(result) == 1

    def test_case_insensitive(self, image_collector):
        image_collector.all_images = [
            self._make_img("1", description="Machine Learning"),
        ]
        result = image_collector.get_images_by_keyword("machine learning")
        assert len(result) == 1

    def test_no_match_returns_empty(self, image_collector):
        image_collector.all_images = [
            self._make_img("1", description="cats and dogs"),
        ]
        result = image_collector.get_images_by_keyword("quantum physics")
        assert result == []

    def test_returns_all_matching(self, image_collector):
        image_collector.all_images = [
            self._make_img("1", description="python tutorial"),
            self._make_img("2", description="python code example"),
            self._make_img("3", description="java tutorial"),
        ]
        result = image_collector.get_images_by_keyword("python")
        assert len(result) == 2


# ===== run() - PDF/URL/keyword paths =====

class TestImageCollectorRun:
    def _make_sources(self, pdfs=None, urls=None, image_keywords=None):
        return {
            "pdfs": pdfs or [],
            "urls": urls or [],
            "image_keywords": image_keywords or [],
        }

    def test_collect_with_no_sources_returns_empty(self, image_collector):
        result = image_collector.collect(
            sources=self._make_sources(),
            auto_describe_images=False, download_search_images=False
        )
        assert result["success"] is True
        assert result["images"] == []

    def test_collect_with_pdf_extraction_error(self, image_collector, tmp_path):
        """PDF extractor failure logs error but continues."""
        pdf_path = str(tmp_path / "test.pdf")
        (tmp_path / "test.pdf").write_bytes(b"%PDF-1.4")

        mock_result = {"success": False, "error": "PDF corrupted", "images": []}
        image_collector.pdf_extractor.run = MagicMock(return_value=mock_result)

        result = image_collector.collect(
            sources=self._make_sources(pdfs=[pdf_path]),
            auto_describe_images=False, download_search_images=False
        )
        assert result["success"] is True  # Continues despite error
        assert result["images"] == []

    def test_collect_with_keyword_pexels_success(self, image_collector):
        """Keyword search via Pexels returns images."""
        mock_pexels_result = {
            "success": True,
            "images": [{"id": "pexels_1", "description": "test", "alt_text": "", "query": "ml"}]
        }
        image_collector.pexels_search.run = MagicMock(return_value=mock_pexels_result)

        result = image_collector.collect(
            sources=self._make_sources(image_keywords=["machine learning"]),
            auto_describe_images=False, download_search_images=False
        )
        assert result["success"] is True
        assert len(result["images"]) == 1

    def test_collect_with_pexels_failure_falls_back_to_unsplash(self, image_collector):
        """When Pexels fails, Unsplash is tried as fallback."""
        mock_pexels_fail = {"success": False, "error": "API error", "images": []}
        mock_unsplash_result = {
            "success": True,
            "images": [{"id": "unsplash_1", "description": "ml", "alt_text": "", "query": "ml"}]
        }
        image_collector.pexels_search.run = MagicMock(return_value=mock_pexels_fail)
        image_collector.unsplash_search.run = MagicMock(return_value=mock_unsplash_result)

        result = image_collector.collect(
            sources=self._make_sources(image_keywords=["machine learning"]),
            auto_describe_images=False, download_search_images=False
        )
        assert result["success"] is True
        assert len(result["images"]) == 1

    def test_collect_stores_images_in_vector_db_when_available(self, image_collector, mock_vector_store):
        """When vector_store is set, _store_images_in_vector_db is called."""
        mock_pexels_result = {
            "success": True,
            "images": [{"id": "pexels_1", "description": "test", "alt_text": "", "query": "ai"}]
        }
        image_collector.pexels_search.run = MagicMock(return_value=mock_pexels_result)

        with patch.object(image_collector, "_store_images_in_vector_db") as mock_store:
            image_collector.collect(
                sources=self._make_sources(image_keywords=["ai"]),
                auto_describe_images=False, download_search_images=False
            )
        mock_store.assert_called_once()

    def test_collect_returns_total_count(self, image_collector):
        mock_pexels_result = {
            "success": True,
            "images": [
                {"id": "pexels_1", "description": "a", "alt_text": "", "query": "q"},
                {"id": "pexels_2", "description": "b", "alt_text": "", "query": "q"},
            ]
        }
        image_collector.pexels_search.run = MagicMock(return_value=mock_pexels_result)

        result = image_collector.collect(
            sources=self._make_sources(image_keywords=["test"]),
            auto_describe_images=False, download_search_images=False
        )
        assert result["total_collected"] == 2

    def test_collect_with_url_success(self, image_collector):
        """URL scraping path: WebScraperTool and web_scraper both succeed."""
        web_img = {"id": "web_abc", "hash": "abc123", "description": "", "alt_text": "", "query": ""}
        mock_scraper_result = {"success": True}
        mock_web_result = {"success": True, "images": [web_img]}

        with patch("lecture_forge.tools.web_scraper.WebScraperTool") as MockScraper:
            MockScraper.return_value.run = MagicMock(return_value=mock_scraper_result)
            with patch("requests.get") as mock_requests_get:
                mock_response = MagicMock()
                mock_response.content = b"<html></html>"
                mock_requests_get.return_value = mock_response
                with patch("bs4.BeautifulSoup", return_value=MagicMock()):
                    image_collector.web_scraper.run = MagicMock(return_value=mock_web_result)
                    result = image_collector.collect(
                        sources=self._make_sources(urls=["https://example.com"]),
                        auto_describe_images=False, download_search_images=False
                    )
        assert result["success"] is True

    def test_collect_with_url_scrape_failure(self, image_collector):
        """URL scraping path: WebScraperTool fails, continues gracefully."""
        mock_scraper_result = {"success": False, "error": "Connection failed"}

        with patch("lecture_forge.tools.web_scraper.WebScraperTool") as MockScraper:
            MockScraper.return_value.run = MagicMock(return_value=mock_scraper_result)
            result = image_collector.collect(
                sources=self._make_sources(urls=["https://example.com"]),
                auto_describe_images=False, download_search_images=False
            )
        assert result["success"] is True
        assert result["images"] == []

    def test_collect_with_url_exception(self, image_collector):
        """URL scraping path: exception is caught and continues."""
        with patch("lecture_forge.tools.web_scraper.WebScraperTool", side_effect=Exception("network error")):
            result = image_collector.collect(
                sources=self._make_sources(urls=["https://example.com"]),
                auto_describe_images=False, download_search_images=False
            )
        assert result["success"] is True

    def test_collect_with_pdf_exception(self, image_collector, tmp_path):
        """PDF extraction path: exception is caught and continues."""
        pdf_path = str(tmp_path / "test.pdf")
        (tmp_path / "test.pdf").write_bytes(b"%PDF-1.4")
        image_collector.pdf_extractor.run = MagicMock(side_effect=Exception("unexpected error"))

        result = image_collector.collect(
            sources=self._make_sources(pdfs=[pdf_path]),
            auto_describe_images=False, download_search_images=False
        )
        assert result["success"] is True

    def test_collect_both_search_fail_logs_warning(self, image_collector):
        """When both Pexels and Unsplash fail, result still succeeds."""
        mock_fail = {"success": False, "error": "API error", "images": []}
        image_collector.pexels_search.run = MagicMock(return_value=mock_fail)
        image_collector.unsplash_search.run = MagicMock(return_value=mock_fail)

        result = image_collector.collect(
            sources=self._make_sources(image_keywords=["test"]),
            auto_describe_images=False, download_search_images=False
        )
        assert result["success"] is True
        assert result["images"] == []

    def test_collect_builds_image_page_map_for_pdf_images(self, image_collector, tmp_path):
        """When PDF images collected, image_page_map is built and saved."""
        pdf_img = {
            "id": "pdf_abc123456",
            "source": str(tmp_path / "doc.pdf"),
            "page": 1,
            "hash": "abc123",
            "path": str(tmp_path / "img.png"),
            "description": "", "alt_text": "", "width": 800, "height": 600,
        }
        mock_pdf_result = {"success": True, "images": [pdf_img]}
        image_collector.pdf_extractor.run = MagicMock(return_value=mock_pdf_result)

        with patch.object(image_collector, "_save_image_page_map") as mock_save:
            result = image_collector.collect(
                sources=self._make_sources(pdfs=[str(tmp_path / "doc.pdf")]),
                auto_describe_images=False, download_search_images=False
            )
        mock_save.assert_called_once()


# ===== _save_image_page_map() =====

class TestSaveImagePageMap:
    def test_saves_map_to_file(self, image_collector, tmp_path):
        from lecture_forge.config import Config
        import json as json_mod

        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            map_data = {"doc.pdf": {"1": [{"id": "img_1"}]}}
            image_collector._save_image_page_map(map_data)
            expected_file = tmp_path / "images" / image_collector.session_id / "image_page_map.json"
            assert expected_file.exists()
            saved = json_mod.loads(expected_file.read_text())
            assert "doc.pdf" in saved
        finally:
            Config.DATA_DIR = original

    def test_does_nothing_for_empty_map(self, image_collector, tmp_path):
        from lecture_forge.config import Config
        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            image_collector._save_image_page_map({})
            # No file should be created
            session_dir = tmp_path / "images" / image_collector.session_id
            assert not (session_dir / "image_page_map.json").exists()
        finally:
            Config.DATA_DIR = original

    def test_handles_write_error_gracefully(self, image_collector, tmp_path):
        from lecture_forge.config import Config
        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            map_data = {"doc.pdf": {"1": [{"id": "img_1"}]}}
            with patch("builtins.open", side_effect=IOError("disk full")):
                # Should not raise
                image_collector._save_image_page_map(map_data)
        finally:
            Config.DATA_DIR = original
