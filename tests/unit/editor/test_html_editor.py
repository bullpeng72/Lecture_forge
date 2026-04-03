"""
Unit tests for LectureHTMLEditor (src/lecture_forge/editor/html_editor.py).
"""

import pytest
from pathlib import Path
from bs4 import BeautifulSoup

from lecture_forge.editor.html_editor import LectureHTMLEditor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Lecture</title></head>
<body>
  <h1>Test Lecture Title</h1>
  <nav>
    <a href="#sec1" class="toc-link">1. Intro</a>
    <a href="#sec2" class="toc-link">2. Body</a>
  </nav>
  <section id="sec1">
    <h2>1. Introduction</h2>
    <p>This is the introduction paragraph with some content here.</p>
  </section>
  <section id="sec2">
    <h2>2. Main Body</h2>
    <p>This is the main body section with more detailed content.</p>
    <figure><img src="img1.png" alt="chart"/><figcaption>Chart 1</figcaption></figure>
  </section>
</body>
</html>"""

DUPLICATE_IDS_HTML = """<!DOCTYPE html>
<html><body>
  <nav>
    <a href="#intro" class="toc-link">Intro A</a>
    <a href="#intro" class="toc-link">Intro B</a>
  </nav>
  <section id="intro"><h2>Section A</h2><p>Content A</p></section>
  <section id="intro"><h2>Section B</h2><p>Content B</p></section>
</body></html>"""

MERMAID_HTML = """<!DOCTYPE html>
<html><body>
  <section id="sec1">
    <h2>Diagrams</h2>
    <p>Some text here.</p>
    <div class="my-8"><div class="mermaid">graph TD\nA --> B</div></div>
  </section>
</body></html>"""


@pytest.fixture
def html_file(tmp_path):
    """Write MINIMAL_HTML to a temp file and return its path."""
    p = tmp_path / "lecture.html"
    p.write_text(MINIMAL_HTML, encoding="utf-8")
    return p


@pytest.fixture
def editor(html_file):
    """Return a LectureHTMLEditor wrapping the minimal HTML file."""
    return LectureHTMLEditor(str(html_file))


@pytest.fixture
def dup_html_file(tmp_path):
    p = tmp_path / "dup.html"
    p.write_text(DUPLICATE_IDS_HTML, encoding="utf-8")
    return p


@pytest.fixture
def mermaid_html_file(tmp_path):
    p = tmp_path / "mermaid.html"
    p.write_text(MERMAID_HTML, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_success(self, html_file):
        editor = LectureHTMLEditor(str(html_file))
        assert editor.html_path == html_file
        assert editor.soup is not None

    def test_init_with_soup(self, html_file):
        soup = BeautifulSoup(MINIMAL_HTML, "html.parser")
        editor = LectureHTMLEditor(str(html_file), soup=soup)
        assert editor.soup is soup

    def test_init_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            LectureHTMLEditor(str(tmp_path / "nonexistent.html"))

    def test_staged_starts_empty(self, editor):
        assert editor._staged == {}

    def test_added_images_starts_empty(self, editor):
        assert editor._added_images == {}


# ---------------------------------------------------------------------------
# _deduplicate_section_ids
# ---------------------------------------------------------------------------

class TestDeduplicateSectionIds:
    def test_duplicate_ids_renamed(self, dup_html_file):
        editor = LectureHTMLEditor(str(dup_html_file))
        sections = editor.soup.find_all("section", id=True)
        ids = [s["id"] for s in sections]
        assert len(set(ids)) == len(ids), "Duplicate IDs should be renamed"

    def test_first_occurrence_unchanged(self, dup_html_file):
        editor = LectureHTMLEditor(str(dup_html_file))
        sections = editor.soup.find_all("section", id=True)
        assert sections[0]["id"] == "intro"

    def test_second_occurrence_renamed(self, dup_html_file):
        editor = LectureHTMLEditor(str(dup_html_file))
        sections = editor.soup.find_all("section", id=True)
        assert sections[1]["id"] != "intro"
        assert sections[1]["id"].startswith("intro_")

    def test_toc_link_updated(self, dup_html_file):
        editor = LectureHTMLEditor(str(dup_html_file))
        links = editor.soup.find_all("a", class_="toc-link")
        hrefs = [a["href"] for a in links]
        assert len(set(hrefs)) == 2, "Both TOC links should point to distinct IDs"

    def test_unique_ids_unchanged(self, editor):
        sections = editor.soup.find_all("section", id=True)
        assert sections[0]["id"] == "sec1"
        assert sections[1]["id"] == "sec2"


# ---------------------------------------------------------------------------
# get_lecture_meta
# ---------------------------------------------------------------------------

class TestGetLectureMeta:
    def test_returns_title(self, editor):
        meta = editor.get_lecture_meta()
        assert meta["title"] == "Test Lecture Title"

    def test_returns_sections_list(self, editor):
        meta = editor.get_lecture_meta()
        assert isinstance(meta["sections"], list)
        assert len(meta["sections"]) == 2

    def test_section_has_expected_keys(self, editor):
        meta = editor.get_lecture_meta()
        sec = meta["sections"][0]
        for key in ("id", "title", "word_count", "image_count", "diagram_count", "status"):
            assert key in sec

    def test_section_status_original(self, editor):
        meta = editor.get_lecture_meta()
        assert meta["sections"][0]["status"] == "original"

    def test_image_count_correct(self, editor):
        meta = editor.get_lecture_meta()
        # sec2 has one img inside a figure
        sec2 = next(s for s in meta["sections"] if s["id"] == "sec2")
        assert sec2["image_count"] == 1

    def test_diagram_count_zero_for_plain_section(self, editor):
        meta = editor.get_lecture_meta()
        sec1 = next(s for s in meta["sections"] if s["id"] == "sec1")
        assert sec1["diagram_count"] == 0

    def test_deleted_section_shows_deleted_status(self, editor):
        editor.delete_section("sec1")
        meta = editor.get_lecture_meta()
        sec1 = next(s for s in meta["sections"] if s["id"] == "sec1")
        assert sec1["status"] == "deleted"

    def test_updated_section_shows_modified_status(self, editor):
        editor.update_section_content("sec1", "new content")
        meta = editor.get_lecture_meta()
        sec1 = next(s for s in meta["sections"] if s["id"] == "sec1")
        assert sec1["status"] == "modified"

    def test_no_h1_returns_untitled(self, tmp_path):
        html = "<html><body><section id='s1'><h2>X</h2><p>y</p></section></body></html>"
        p = tmp_path / "no_h1.html"
        p.write_text(html, encoding="utf-8")
        editor = LectureHTMLEditor(str(p))
        meta = editor.get_lecture_meta()
        assert meta["title"] == "Untitled"


# ---------------------------------------------------------------------------
# get_section_content
# ---------------------------------------------------------------------------

class TestGetSectionContent:
    def test_returns_section_content(self, editor):
        result = editor.get_section_content("sec1")
        assert result["id"] == "sec1"
        assert "title" in result
        assert "markdown" in result

    def test_unknown_section_returns_error(self, editor):
        result = editor.get_section_content("nonexistent")
        assert "error" in result

    def test_markdown_contains_text(self, editor):
        result = editor.get_section_content("sec1")
        assert "introduction" in result["markdown"].lower()

    def test_staged_modification_returned(self, editor):
        editor.update_section_content("sec1", "# Updated content", title="New Title")
        result = editor.get_section_content("sec1")
        assert result["status"] == "modified"
        assert result["markdown"] == "# Updated content"
        assert result["title"] == "New Title"

    def test_word_count_returned(self, editor):
        result = editor.get_section_content("sec1")
        assert isinstance(result["word_count"], int)
        assert result["word_count"] > 0


# ---------------------------------------------------------------------------
# update_section_content
# ---------------------------------------------------------------------------

class TestUpdateSectionContent:
    def test_update_success(self, editor):
        result = editor.update_section_content("sec1", "New markdown content")
        assert result["success"] is True
        assert result["section_id"] == "sec1"

    def test_update_nonexistent_section(self, editor):
        result = editor.update_section_content("nope", "content")
        assert result["success"] is False
        assert "error" in result

    def test_update_preserves_title_when_not_given(self, editor):
        editor.update_section_content("sec1", "content")
        staged = editor._staged["sec1"]
        assert staged["title"] == "1. Introduction"

    def test_update_uses_provided_title(self, editor):
        editor.update_section_content("sec1", "content", title="My Title")
        staged = editor._staged["sec1"]
        assert staged["title"] == "My Title"

    def test_update_stores_markdown(self, editor):
        editor.update_section_content("sec1", "## Hello\n\nWorld")
        assert editor._staged["sec1"]["markdown"] == "## Hello\n\nWorld"


# ---------------------------------------------------------------------------
# delete_section
# ---------------------------------------------------------------------------

class TestDeleteSection:
    def test_delete_existing_section(self, editor):
        result = editor.delete_section("sec1")
        assert result is True
        assert editor._staged["sec1"] == "deleted"

    def test_delete_nonexistent_section(self, editor):
        result = editor.delete_section("ghost")
        assert result is False

    def test_delete_marks_staged(self, editor):
        editor.delete_section("sec2")
        assert editor._staged["sec2"] == "deleted"


# ---------------------------------------------------------------------------
# stage_add_image / unstage_add_image / get_pending_additions
# ---------------------------------------------------------------------------

class TestImageStaging:
    def test_stage_add_image_success(self, editor):
        ok = editor.stage_add_image("sec1", "/img/foo.png", "Caption")
        assert ok is True
        assert len(editor._added_images["sec1"]) == 1

    def test_stage_add_image_nonexistent_section(self, editor):
        ok = editor.stage_add_image("nope", "/img/foo.png")
        assert ok is False

    def test_stage_multiple_images(self, editor):
        editor.stage_add_image("sec1", "/img/a.png", "A")
        editor.stage_add_image("sec1", "/img/b.png", "B")
        assert len(editor._added_images["sec1"]) == 2

    def test_unstage_image(self, editor):
        editor.stage_add_image("sec1", "/img/a.png")
        editor.stage_add_image("sec1", "/img/b.png")
        result = editor.unstage_add_image("sec1", 0)
        assert result is True
        assert len(editor._added_images["sec1"]) == 1

    def test_unstage_out_of_range(self, editor):
        editor.stage_add_image("sec1", "/img/a.png")
        result = editor.unstage_add_image("sec1", 5)
        assert result is False

    def test_get_pending_additions_empty(self, editor):
        assert editor.get_pending_additions("sec1") == []

    def test_get_pending_additions_returns_copy(self, editor):
        editor.stage_add_image("sec1", "/img/a.png", "A")
        pending = editor.get_pending_additions("sec1")
        assert pending[0]["path"] == "/img/a.png"
        assert pending[0]["caption"] == "A"


# ---------------------------------------------------------------------------
# apply_all_changes
# ---------------------------------------------------------------------------

class TestApplyAllChanges:
    def test_apply_deletion_removes_section(self, editor):
        editor.delete_section("sec1")
        soup = editor.apply_all_changes()
        assert soup.find("section", id="sec1") is None

    def test_apply_deletion_removes_toc_entry(self, editor):
        editor.delete_section("sec1")
        editor.apply_all_changes()
        link = editor.soup.find("a", href="#sec1")
        assert link is None

    def test_apply_content_update(self, editor):
        editor.update_section_content("sec1", "Updated paragraph text here.", title="Updated Title")
        editor.apply_all_changes()
        sec1 = editor.soup.find("section", id="sec1")
        assert sec1 is not None
        # h2 should reflect new title (prefix preserved + stripped new title)
        h2 = sec1.find("h2")
        assert "Updated Title" in h2.get_text()

    def test_apply_image_addition(self, editor):
        editor.stage_add_image("sec1", "/img/new.png", "New image")
        editor.apply_all_changes()
        sec1 = editor.soup.find("section", id="sec1")
        img = sec1.find("img", src="/img/new.png")
        assert img is not None

    def test_apply_image_caption(self, editor):
        editor.stage_add_image("sec1", "/img/cap.png", "My Caption")
        editor.apply_all_changes()
        sec1 = editor.soup.find("section", id="sec1")
        figcap = sec1.find("figcaption")
        assert figcap is not None
        assert "My Caption" in figcap.get_text()

    def test_apply_no_changes_idempotent(self, editor):
        result = editor.apply_all_changes()
        # No sections removed, HTML still valid
        assert result.find("section", id="sec1") is not None

    def test_apply_update_toc_title(self, editor):
        editor.update_section_content("sec1", "content", title="Brand New Title")
        editor.apply_all_changes()
        link = editor.soup.find("a", href="#sec1")
        assert link is not None
        assert "Brand New Title" in link.get_text()


# ---------------------------------------------------------------------------
# _html_section_to_markdown (via get_section_content)
# ---------------------------------------------------------------------------

class TestHtmlSectionToMarkdown:
    def test_figure_excluded(self, editor):
        result = editor.get_section_content("sec2")
        # Figure/img tags should not appear literally in markdown
        assert "<figure" not in result["markdown"]
        assert "<img" not in result["markdown"]

    def test_mermaid_excluded(self, mermaid_html_file):
        editor = LectureHTMLEditor(str(mermaid_html_file))
        result = editor.get_section_content("sec1")
        assert "mermaid" not in result["markdown"].lower()

    def test_h2_excluded_from_markdown(self, editor):
        result = editor.get_section_content("sec1")
        # The h2 title text should not appear in the markdown body
        # (it's kept in the 'title' field separately)
        assert "<h2" not in result["markdown"]


# ---------------------------------------------------------------------------
# _markdown_to_section_html (indirectly via apply)
# ---------------------------------------------------------------------------

class TestMarkdownToSectionHtml:
    def test_bold_converted(self, editor):
        editor.update_section_content("sec1", "**bold text** here")
        editor.apply_all_changes()
        sec1 = editor.soup.find("section", id="sec1")
        assert sec1.find("strong") is not None

    def test_list_converted(self, editor):
        editor.update_section_content("sec1", "- item one\n- item two")
        editor.apply_all_changes()
        sec1 = editor.soup.find("section", id="sec1")
        assert sec1.find("li") is not None


# ---------------------------------------------------------------------------
# _update_stats
# ---------------------------------------------------------------------------

class TestUpdateStats:
    def test_stats_updated_after_deletion(self, tmp_path):
        html = """<html><body>
        <span>섹션 2개</span>
        <section id="s1"><h2>A</h2><p>text</p></section>
        <section id="s2"><h2>B</h2><p>text</p></section>
        </body></html>"""
        p = tmp_path / "stats.html"
        p.write_text(html, encoding="utf-8")
        editor = LectureHTMLEditor(str(p))
        editor.delete_section("s1")
        editor.apply_all_changes()
        text = editor.soup.get_text()
        assert "섹션 1개" in text
