"""
Unit tests for image extractor tools.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPDFImageExtractorTool:
    def test_initializes_with_custom_output_dir(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_extractor import PDFImageExtractorTool

        tool = PDFImageExtractorTool(output_dir=str(temp_dir))
        assert tool.output_dir == temp_dir

    def test_initializes_with_default_output_dir(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_extractor import PDFImageExtractorTool

        with patch("lecture_forge.tools.image_extractor.Config") as mock_config:
            mock_config.DATA_DIR = temp_dir
            mock_config.IMAGE_MIN_WIDTH = 500
            mock_config.IMAGE_MIN_HEIGHT = 300
            mock_config.IMAGE_EXTRACTION_QUALITY_THRESHOLD = 50
            tool = PDFImageExtractorTool()
            assert tool.output_dir == temp_dir / "images"

    def test_initializes_stats(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_extractor import PDFImageExtractorTool

        tool = PDFImageExtractorTool(output_dir=str(temp_dir))
        assert "total_found" in tool.stats
        assert "extracted" in tool.stats
        assert tool.stats["extracted"] == 0

    def test_run_returns_error_for_nonexistent_file(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_extractor import PDFImageExtractorTool

        tool = PDFImageExtractorTool(output_dir=str(temp_dir))
        result = tool.run("/nonexistent/path/file.pdf")

        assert result["success"] is False
        assert result["images"] == []
        assert "error" in result

    def test_run_with_zero_page_pdf_returns_empty(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_extractor import PDFImageExtractorTool

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=0)
        mock_doc.__iter__ = MagicMock(return_value=iter([]))

        with patch("fitz.open", return_value=mock_doc):
            tool = PDFImageExtractorTool(output_dir=str(temp_dir))
            # Create a fake file so path.exists() passes
            fake_pdf = temp_dir / "test.pdf"
            fake_pdf.write_bytes(b"%PDF-1.4\n")
            result = tool.run(str(fake_pdf))

        assert result["images"] == []

    def test_tool_has_name_and_description(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_extractor import PDFImageExtractorTool

        tool = PDFImageExtractorTool(output_dir=str(temp_dir))
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")


class TestWebImageScraperTool:
    def test_initializes_with_config_defaults(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_extractor import WebImageScraperTool

        with patch("lecture_forge.tools.image_extractor.Config") as mock_config:
            mock_config.DATA_DIR = temp_dir
            mock_config.IMAGE_MIN_WIDTH = 500
            mock_config.IMAGE_MIN_HEIGHT = 300
            mock_config.IMAGE_EXTRACTION_QUALITY_THRESHOLD = 50
            tool = WebImageScraperTool(output_dir=str(temp_dir))
            assert tool.min_width == 500
            assert tool.min_height == 300

    def test_run_with_no_img_tags_returns_empty(self, test_env_vars, temp_dir):
        from bs4 import BeautifulSoup

        from lecture_forge.tools.image_extractor import WebImageScraperTool

        tool = WebImageScraperTool(output_dir=str(temp_dir))

        # WebImageScraperTool.run() takes (url, soup, session_id)
        soup = BeautifulSoup("<html><body><p>No images here</p></body></html>", "html.parser")
        result = tool.run("https://example.com", soup)

        assert result["images"] == []

    def test_run_returns_expected_keys(self, test_env_vars, temp_dir):
        from bs4 import BeautifulSoup

        from lecture_forge.tools.image_extractor import WebImageScraperTool

        tool = WebImageScraperTool(output_dir=str(temp_dir))

        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        result = tool.run("https://example.com", soup)

        assert "images" in result
