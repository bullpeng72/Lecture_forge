"""
Unit tests for PDFImageDescriberTool - pure logic methods.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def describer(test_env_vars):
    """Create PDFImageDescriber instance with mocked OpenAI."""
    from lecture_forge.tools.pdf_image_describer import PDFImageDescriber
    with patch("lecture_forge.tools.pdf_image_describer.fitz"):
        with patch("openai.OpenAI"):
            return PDFImageDescriber()


# ===== _group_images_by_page() =====

class TestGroupImagesByPage:
    def test_empty_dir_returns_empty(self, tmp_path, describer):
        result = describer._group_images_by_page(tmp_path)
        assert result == {}

    def test_groups_single_page(self, tmp_path, describer):
        (tmp_path / "page1_img1_abc.png").write_bytes(b"")
        result = describer._group_images_by_page(tmp_path)
        assert 1 in result
        assert len(result[1]) == 1

    def test_groups_multiple_images_same_page(self, tmp_path, describer):
        (tmp_path / "page2_img1_abc.png").write_bytes(b"")
        (tmp_path / "page2_img2_def.png").write_bytes(b"")
        result = describer._group_images_by_page(tmp_path)
        assert 2 in result
        assert len(result[2]) == 2

    def test_groups_multiple_pages(self, tmp_path, describer):
        (tmp_path / "page1_img1_abc.png").write_bytes(b"")
        (tmp_path / "page3_img1_xyz.png").write_bytes(b"")
        result = describer._group_images_by_page(tmp_path)
        assert 1 in result
        assert 3 in result

    def test_supports_webp_format(self, tmp_path, describer):
        (tmp_path / "page5_img1_abc.webp").write_bytes(b"")
        result = describer._group_images_by_page(tmp_path)
        assert 5 in result

    def test_supports_jpg_format(self, tmp_path, describer):
        (tmp_path / "page6_img1_abc.jpg").write_bytes(b"")
        result = describer._group_images_by_page(tmp_path)
        assert 6 in result

    def test_ignores_non_image_files(self, tmp_path, describer):
        (tmp_path / "readme.txt").write_text("not an image")
        (tmp_path / "data.json").write_text("{}")
        result = describer._group_images_by_page(tmp_path)
        assert result == {}

    def test_ignores_files_not_starting_with_page(self, tmp_path, describer):
        (tmp_path / "random_image.png").write_bytes(b"")
        result = describer._group_images_by_page(tmp_path)
        assert result == {}

    def test_returns_path_objects(self, tmp_path, describer):
        (tmp_path / "page1_img1_abc.png").write_bytes(b"")
        result = describer._group_images_by_page(tmp_path)
        assert all(isinstance(p, Path) for p in result[1])


# ===== _parse_descriptions() =====

class TestParseDescriptions:
    def test_parses_image_format(self, describer):
        text = "Image 1: First description.\nImage 2: Second description."
        result = describer._parse_descriptions(text, 2)
        assert len(result) == 2
        assert result[0] == "First description."
        assert result[1] == "Second description."

    def test_pads_to_expected_count(self, describer):
        text = "Image 1: Only one description."
        result = describer._parse_descriptions(text, 3)
        assert len(result) == 3
        # Padded with last description
        assert result[1] == result[2] == "Only one description."

    def test_truncates_to_expected_count(self, describer):
        text = "Image 1: D1.\nImage 2: D2.\nImage 3: D3.\nImage 4: D4."
        result = describer._parse_descriptions(text, 2)
        assert len(result) == 2

    def test_fallback_when_no_image_prefix(self, describer):
        text = "A diagram showing. Another element. Third part."
        result = describer._parse_descriptions(text, 2)
        assert len(result) == 2

    def test_empty_fallback_when_no_content(self, describer):
        text = ""
        result = describer._parse_descriptions(text, 2)
        assert len(result) == 2  # padded with generic
        assert isinstance(result[0], str)

    def test_returns_list(self, describer):
        result = describer._parse_descriptions("Image 1: desc.", 1)
        assert isinstance(result, list)

    def test_single_description(self, describer):
        text = "Image 1: Single image description here."
        result = describer._parse_descriptions(text, 1)
        assert len(result) == 1
        assert result[0] == "Single image description here."


# ===== __init__() and enhance_images() =====

class TestPDFImageDescriberInit:
    def test_raises_without_api_key(self, test_env_vars):
        """Missing OPENAI_API_KEY raises ValueError."""
        from lecture_forge.tools.pdf_image_describer import PDFImageDescriber
        from lecture_forge.config import Config
        original = Config.OPENAI_API_KEY
        try:
            Config.OPENAI_API_KEY = None
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                with patch("openai.OpenAI"):
                    PDFImageDescriber()
        finally:
            Config.OPENAI_API_KEY = original


class TestEnhanceImages:
    """Tests for enhance_images() error branches."""

    def test_returns_error_when_pdf_not_found(self, tmp_path, describer):
        result = describer.enhance_images(str(tmp_path / "nonexistent.pdf"), str(tmp_path))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_returns_error_when_image_dir_not_found(self, tmp_path, describer):
        # Create a real PDF file path that "exists" but image_dir doesn't
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")
        result = describer.enhance_images(str(fake_pdf), str(tmp_path / "no_images"))
        assert result["success"] is False
        assert "image directory" in result["error"].lower()

    def test_returns_error_when_fitz_open_fails(self, tmp_path, describer):
        fake_pdf = tmp_path / "bad.pdf"
        fake_pdf.write_bytes(b"not a pdf")
        with patch("lecture_forge.tools.pdf_image_describer.fitz") as mock_fitz:
            mock_fitz.open.side_effect = Exception("corrupt pdf")
            result = describer.enhance_images(str(fake_pdf), str(tmp_path))
        assert result["success"] is False
        assert "Failed to open PDF" in result["error"]

    def test_success_with_no_images(self, tmp_path, describer):
        """PDF opens but has no images → returns success with 0 enhanced."""
        fake_pdf = tmp_path / "empty.pdf"
        fake_pdf.write_bytes(b"fake")

        mock_doc = MagicMock()
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.close = MagicMock()

        with patch("lecture_forge.tools.pdf_image_describer.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = describer.enhance_images(str(fake_pdf), str(tmp_path))
        assert result["success"] is True
        assert result["enhanced_count"] == 0

    def test_page_exception_continues_to_next(self, tmp_path, describer):
        """Exception on one page is caught, processing continues."""
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")
        (tmp_path / "page1_img1_abc.png").write_bytes(b"fake_img")

        mock_doc = MagicMock()
        mock_doc.close = MagicMock()

        with patch("lecture_forge.tools.pdf_image_describer.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            # Make _extract_page_text raise
            with patch.object(describer, "_extract_page_text", side_effect=Exception("page error")):
                result = describer.enhance_images(str(fake_pdf), str(tmp_path))
        # Should still return success (exception was caught per-page)
        assert result is not None


class TestApplyDescriptionsToImages:
    """Tests for apply_descriptions_to_images()."""

    def test_returns_0_when_no_descriptions_file(self, tmp_path, describer):
        result = describer.apply_descriptions_to_images(str(tmp_path))
        assert result == 0

    def test_loads_and_returns_count(self, tmp_path, describer):
        import json
        desc_data = [
            {"file": "page1_img1.png", "description": "Diagram"},
            {"file": "page2_img1.png", "description": "Chart"},
        ]
        desc_file = tmp_path / "image_descriptions.json"
        desc_file.write_text(json.dumps(desc_data))

        result = describer.apply_descriptions_to_images(str(tmp_path))
        assert result == 2

    def test_returns_0_on_json_parse_error(self, tmp_path, describer):
        desc_file = tmp_path / "image_descriptions.json"
        desc_file.write_text("not valid json")
        result = describer.apply_descriptions_to_images(str(tmp_path))
        assert result == 0

    def test_uses_custom_descriptions_file(self, tmp_path, describer):
        import json
        desc_data = [{"file": "img.png", "description": "Test"}]
        custom_file = tmp_path / "custom_desc.json"
        custom_file.write_text(json.dumps(desc_data))

        result = describer.apply_descriptions_to_images(str(tmp_path), str(custom_file))
        assert result == 1

    def test_missing_custom_file_returns_0(self, tmp_path, describer):
        result = describer.apply_descriptions_to_images(
            str(tmp_path), str(tmp_path / "missing.json")
        )
        assert result == 0


class TestExtractPageText:
    """Tests for _extract_page_text() exception branch."""

    def test_returns_empty_on_exception(self, describer):
        mock_doc = MagicMock()
        mock_doc.__getitem__.side_effect = Exception("index error")
        result = describer._extract_page_text(mock_doc, 1)
        assert result == ""

    def test_returns_text_on_success(self, describer):
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page text content"
        mock_doc = MagicMock()
        mock_doc.__getitem__.return_value = mock_page
        result = describer._extract_page_text(mock_doc, 1)
        assert result == "Page text content"


class TestGenerateDescriptionsForPage:
    """Tests for _generate_descriptions_for_page() exception path."""

    def test_llm_exception_returns_generic(self, describer):
        describer.client = MagicMock()
        describer.client.chat.completions.create.side_effect = Exception("LLM error")
        result = describer._generate_descriptions_for_page(1, "Some page text", 2)
        assert len(result) == 2
        assert all("page 1" in r for r in result)
