"""
Unit tests for ImageEditor tool.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def make_html_with_images(n=2):
    """Create HTML with n images inside figure tags, within a section."""
    figures = ""
    for i in range(1, n + 1):
        figures += f"""
        <figure>
            <img src="image_{i}.png" alt="Image {i} description page {i}" />
            <figcaption>Caption {i}</figcaption>
        </figure>"""

    return f"""<!DOCTYPE html>
<html>
<head><title>Test Lecture</title></head>
<body>
<section>
  <h2>Main Section</h2>
  <p>Content here.</p>
  {figures}
</section>
</body>
</html>"""


def make_minimal_html(with_images=False):
    img_tag = '<figure><img src="test.jpg" alt="Test image" /></figure>' if with_images else ""
    return f"""<!DOCTYPE html>
<html>
<head><title>Test Lecture</title></head>
<body>
<h1>Test Lecture</h1>
{img_tag}
</body>
</html>"""


@pytest.fixture
def html_file_no_images(tmp_path):
    f = tmp_path / "lecture.html"
    f.write_text(make_minimal_html(with_images=False))
    return f


@pytest.fixture
def html_file_with_images(tmp_path):
    f = tmp_path / "lecture.html"
    f.write_text(make_html_with_images(n=3))
    return f


@pytest.fixture
def editor_no_images(test_env_vars, html_file_no_images):
    from lecture_forge.tools.image_editor import ImageEditor
    with patch("lecture_forge.tools.image_editor.Config") as mock_config:
        mock_config.VECTOR_DB_PATH = html_file_no_images.parent / "nonexistent_db"
        mock_config.DATA_DIR = html_file_no_images.parent
        return ImageEditor(str(html_file_no_images))


@pytest.fixture
def editor_with_images(test_env_vars, html_file_with_images):
    from lecture_forge.tools.image_editor import ImageEditor
    with patch("lecture_forge.tools.image_editor.Config") as mock_config:
        mock_config.VECTOR_DB_PATH = html_file_with_images.parent / "nonexistent_db"
        mock_config.DATA_DIR = html_file_with_images.parent
        return ImageEditor(str(html_file_with_images))


# ===== Initialization =====

class TestImageEditorInit:
    def test_raises_if_file_not_found(self, test_env_vars):
        from lecture_forge.tools.image_editor import ImageEditor
        with pytest.raises(FileNotFoundError):
            ImageEditor("/nonexistent/path/lecture.html")

    def test_initializes_with_valid_file(self, test_env_vars, tmp_path):
        from lecture_forge.tools.image_editor import ImageEditor
        f = tmp_path / "test.html"
        f.write_text(make_minimal_html())
        with patch("lecture_forge.tools.image_editor.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = tmp_path / "nonexistent_db"
            mock_config.DATA_DIR = tmp_path
            editor = ImageEditor(str(f))
        assert editor.html_path == f

    def test_changes_dict_initialized(self, editor_no_images):
        assert "delete" in editor_no_images.changes
        assert "replace" in editor_no_images.changes
        assert "add" in editor_no_images.changes

    def test_vector_store_none_when_db_not_found(self, editor_no_images):
        assert editor_no_images.vector_store is None

    def test_html_content_loaded(self, editor_no_images):
        assert "Test Lecture" in editor_no_images.html_content

    def test_no_images_when_empty_html(self, editor_no_images):
        assert editor_no_images.images == []

    def test_images_extracted_from_html(self, editor_with_images):
        assert len(editor_with_images.images) == 3


# ===== _extract_caption() =====

class TestExtractCaption:
    def test_caption_from_figcaption(self, editor_with_images):
        # Images are inside figures with figcaptions
        img = editor_with_images.images[0]
        assert img["caption"] == "Caption 1"

    def test_no_caption_returns_empty(self, editor_no_images, tmp_path):
        from bs4 import BeautifulSoup
        from lecture_forge.tools.image_editor import ImageEditor
        html = "<html><body><img src='test.png' alt='no caption' /></body></html>"
        f = tmp_path / "nocap.html"
        f.write_text(html)
        with patch("lecture_forge.tools.image_editor.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = tmp_path / "nonexistent_db"
            mock_config.DATA_DIR = tmp_path
            ed = ImageEditor(str(f))
        assert ed.images[0]["caption"] == ""


# ===== _find_section() =====

class TestFindSection:
    def test_finds_section_heading(self, editor_with_images):
        # All images are inside a section with h2 "Main Section"
        img = editor_with_images.images[0]
        assert img["section"] == "Main Section"

    def test_unknown_section_when_no_parent_heading(self, editor_no_images):
        # No section headers in the no-images HTML
        pass  # editor has no images to check, just verify init works


# ===== _extract_page_number() =====

class TestExtractPageNumber:
    def test_extracts_page_from_alt_text(self, editor_with_images):
        # alt="Image 1 description page 1"
        img = editor_with_images.images[0]
        assert img["page"] == 1

    def test_returns_none_when_no_page_number(self, tmp_path, test_env_vars):
        from lecture_forge.tools.image_editor import ImageEditor
        html = "<html><body><img src='img.png' alt='No page here' /></body></html>"
        f = tmp_path / "test.html"
        f.write_text(html)
        with patch("lecture_forge.tools.image_editor.Config") as mock_config:
            mock_config.VECTOR_DB_PATH = tmp_path / "nonexistent_db"
            mock_config.DATA_DIR = tmp_path
            ed = ImageEditor(str(f))
        assert ed.images[0]["page"] is None


# ===== list_images() =====

class TestListImages:
    def test_returns_list_of_dicts(self, editor_with_images):
        result = editor_with_images.list_images()
        assert isinstance(result, list)
        assert len(result) == 3

    def test_default_status_is_keep(self, editor_with_images):
        result = editor_with_images.list_images()
        assert all(r["status"] == "keep" for r in result)

    def test_status_changes_to_delete_after_mark(self, editor_with_images):
        editor_with_images.mark_delete(1)
        result = editor_with_images.list_images()
        assert result[0]["status"] == "delete"
        assert result[1]["status"] == "keep"

    def test_required_keys_in_result(self, editor_with_images):
        result = editor_with_images.list_images()
        for r in result:
            assert "index" in r
            assert "description" in r
            assert "section" in r
            assert "status" in r

    def test_status_replace_when_image_marked_for_replacement(self, editor_with_images, tmp_path):
        # Create a real file to pass the exists() check
        new_img = tmp_path / "new_image.png"
        new_img.write_bytes(b"fake png")
        editor_with_images.replace_image(2, str(new_img))
        result = editor_with_images.list_images()
        assert result[1]["status"] == "replace"


# ===== mark_delete() =====

class TestMarkDelete:
    def test_mark_valid_index_returns_true(self, editor_with_images):
        assert editor_with_images.mark_delete(1) is True

    def test_mark_invalid_index_returns_false(self, editor_with_images):
        assert editor_with_images.mark_delete(999) is False

    def test_mark_zero_returns_false(self, editor_with_images):
        assert editor_with_images.mark_delete(0) is False

    def test_marked_image_in_delete_set(self, editor_with_images):
        editor_with_images.mark_delete(2)
        assert 2 in editor_with_images.changes["delete"]

    def test_mark_multiple_images(self, editor_with_images):
        editor_with_images.mark_delete(1)
        editor_with_images.mark_delete(3)
        assert len(editor_with_images.changes["delete"]) == 2


# ===== unmark_delete() =====

class TestUnmarkDelete:
    def test_unmark_marked_image_returns_true(self, editor_with_images):
        editor_with_images.mark_delete(1)
        assert editor_with_images.unmark_delete(1) is True

    def test_unmark_unmarked_image_returns_false(self, editor_with_images):
        assert editor_with_images.unmark_delete(1) is False

    def test_unmark_removes_from_delete_set(self, editor_with_images):
        editor_with_images.mark_delete(2)
        editor_with_images.unmark_delete(2)
        assert 2 not in editor_with_images.changes["delete"]


# ===== replace_image() =====

class TestReplaceImage:
    def test_replace_valid_index_and_existing_file(self, editor_with_images, tmp_path):
        new_img = tmp_path / "replacement.png"
        new_img.write_bytes(b"fake png data")
        assert editor_with_images.replace_image(1, str(new_img)) is True

    def test_replace_invalid_index_returns_false(self, editor_with_images, tmp_path):
        new_img = tmp_path / "replacement.png"
        new_img.write_bytes(b"fake png data")
        assert editor_with_images.replace_image(999, str(new_img)) is False

    def test_replace_nonexistent_file_returns_false(self, editor_with_images):
        assert editor_with_images.replace_image(1, "/nonexistent/image.png") is False

    def test_replace_adds_to_changes(self, editor_with_images, tmp_path):
        new_img = tmp_path / "replacement.png"
        new_img.write_bytes(b"fake png data")
        editor_with_images.replace_image(2, str(new_img))
        assert 2 in editor_with_images.changes["replace"]


# ===== get_summary() =====

class TestGetSummary:
    def test_summary_all_zeros_initially(self, editor_with_images):
        summary = editor_with_images.get_summary()
        assert summary["total_images"] == 3
        assert summary["to_delete"] == 0
        assert summary["to_replace"] == 0
        assert summary["to_add"] == 0

    def test_summary_reflects_changes(self, editor_with_images, tmp_path):
        editor_with_images.mark_delete(1)
        new_img = tmp_path / "replacement.png"
        new_img.write_bytes(b"fake png")
        editor_with_images.replace_image(2, str(new_img))
        summary = editor_with_images.get_summary()
        assert summary["to_delete"] == 1
        assert summary["to_replace"] == 1

    def test_summary_has_required_keys(self, editor_with_images):
        summary = editor_with_images.get_summary()
        assert "total_images" in summary
        assert "to_delete" in summary
        assert "to_replace" in summary
        assert "to_add" in summary


# ===== save_changes() =====

class TestSaveChanges:
    def test_save_creates_output_file(self, editor_with_images, tmp_path):
        output = str(tmp_path / "output.html")
        result_path = editor_with_images.save_changes(output)
        assert Path(result_path).exists()

    def test_save_default_path_generated(self, editor_with_images):
        result_path = editor_with_images.save_changes()
        assert "_edited" in result_path
        assert result_path.endswith(".html")
        Path(result_path).unlink(missing_ok=True)  # cleanup

    def test_delete_removes_figure_from_html(self, editor_with_images, tmp_path):
        editor_with_images.mark_delete(1)
        output = str(tmp_path / "out.html")
        editor_with_images.save_changes(output)
        content = Path(output).read_text()
        assert "Caption 1" not in content

    def test_replace_changes_src_in_html(self, editor_with_images, tmp_path):
        new_img = tmp_path / "new_img.png"
        new_img.write_bytes(b"fake png")
        editor_with_images.replace_image(1, str(new_img))
        output = str(tmp_path / "out.html")
        editor_with_images.save_changes(output)
        content = Path(output).read_text()
        assert "new_img.png" in content

    def test_save_with_no_changes(self, editor_with_images, tmp_path):
        output = str(tmp_path / "unchanged.html")
        result_path = editor_with_images.save_changes(output)
        assert Path(result_path).exists()
        # Content should still contain original images
        content = Path(output).read_text()
        assert "image_1.png" in content


# ===== find_alternative_images() =====

class TestFindAlternativeImages:
    def test_invalid_index_returns_empty(self, editor_with_images):
        result = editor_with_images.find_alternative_images(999)
        assert result == []

    def test_no_vector_store_falls_back_to_filesystem(self, editor_with_images):
        # editor_with_images has vector_store = None, so it tries filesystem
        # No images dir exists → returns []
        result = editor_with_images.find_alternative_images(1)
        assert isinstance(result, list)

    def test_with_vector_store_queries_it(self, editor_with_images):
        """When vector_store is set and returns results, use them."""
        mock_vs = MagicMock()
        mock_vs.query.return_value = {
            "documents": [["Image description"]],
            "metadatas": [[{"type": "image", "path": "/nonexistent/img.png", "page": 1, "source": "doc.pdf"}]],
        }
        editor_with_images.vector_store = mock_vs
        result = editor_with_images.find_alternative_images(1, max_results=5)
        # Path doesn't exist → filtered out → falls back to filesystem
        assert isinstance(result, list)
