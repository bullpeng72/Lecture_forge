"""
Unit tests for translate CLI command.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def pdf_path(tmp_path):
    f = tmp_path / "paper.pdf"
    f.write_bytes(b"%PDF-1.4")
    return str(f)


def _make_mock_result():
    return {
        "html_path": "/out/lecture_ko.html",
        "sections_count": 5,
        "total_words": 3000,
        "diagrams": 2,
        "images": 4,
        "quality_score": 82.0,
        "token_usage": {"total_tokens": 5000, "total_cost": 0.01},
    }


def _patch_translate_lecture(result=None):
    """Context manager that patches translate_lecture."""
    if result is None:
        result = _make_mock_result()
    return patch(
        "lecture_forge.cli.commands.translate.translate_lecture",
        return_value=result,
    )


# ──────────────────────────────────────────────────────────────────────────────
# translate CLI wrapper
# ──────────────────────────────────────────────────────────────────────────────

class TestTranslateCommand:
    def test_basic_success(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture():
            result = runner.invoke(translate, [pdf_path])
        assert result.exit_code == 0
        assert "Translation complete" in result.output

    def test_shows_statistics(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture():
            result = runner.invoke(translate, [pdf_path])
        assert "Sections: 5" in result.output
        assert "3,000" in result.output or "3000" in result.output

    def test_no_translate_flag(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture() as mock_fn:
            result = runner.invoke(translate, [pdf_path, "--no-translate"])
        assert result.exit_code == 0
        _, kwargs = mock_fn.call_args
        assert kwargs.get("no_translate") is True

    def test_with_slides_flag(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture() as mock_fn:
            result = runner.invoke(translate, [pdf_path, "--with-slides"])
        assert result.exit_code == 0
        _, kwargs = mock_fn.call_args
        assert kwargs.get("with_slides") is True

    def test_with_diagrams_flag(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture() as mock_fn:
            result = runner.invoke(translate, [pdf_path, "--with-diagrams"])
        assert result.exit_code == 0
        _, kwargs = mock_fn.call_args
        assert kwargs.get("with_diagrams") is True

    def test_quality_level_strict(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture() as mock_fn:
            result = runner.invoke(translate, [pdf_path, "--quality-level", "strict"])
        assert result.exit_code == 0
        _, kwargs = mock_fn.call_args
        assert kwargs.get("quality_level") == "strict"

    def test_audience_level_beginner(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture() as mock_fn:
            result = runner.invoke(translate, [pdf_path, "--audience-level", "beginner"])
        assert result.exit_code == 0
        _, kwargs = mock_fn.call_args
        assert kwargs.get("audience_level") == "beginner"

    def test_output_name_passed(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture() as mock_fn:
            result = runner.invoke(translate, [pdf_path, "-o", "my_lecture"])
        assert result.exit_code == 0
        _, kwargs = mock_fn.call_args
        assert kwargs.get("output_name") == "my_lecture"

    def test_error_exits_with_code_1(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with patch("lecture_forge.cli.commands.translate.translate_lecture",
                   side_effect=RuntimeError("boom")):
            result = runner.invoke(translate, [pdf_path])
        assert result.exit_code == 1

    def test_quality_score_shown(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture():
            result = runner.invoke(translate, [pdf_path])
        assert "82" in result.output or "Quality score" in result.output

    def test_zero_quality_score_hidden(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        result_data = _make_mock_result()
        result_data["quality_score"] = 0
        with patch("lecture_forge.cli.commands.translate.translate_lecture",
                   return_value=result_data):
            result = runner.invoke(translate, [pdf_path])
        assert result.exit_code == 0

    def test_no_token_usage(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        result_data = _make_mock_result()
        result_data["token_usage"] = None
        with patch("lecture_forge.cli.commands.translate.translate_lecture",
                   return_value=result_data):
            result = runner.invoke(translate, [pdf_path])
        assert result.exit_code == 0

    def test_header_printed(self, runner, pdf_path):
        from lecture_forge.cli.commands.translate import translate
        with _patch_translate_lecture():
            result = runner.invoke(translate, [pdf_path])
        assert "PDF" in result.output or "LectureForge" in result.output


# ──────────────────────────────────────────────────────────────────────────────
# translate_lecture core function
# ──────────────────────────────────────────────────────────────────────────────

def _make_section_content(section_id="s0", word_count=100, images=None, diagrams=None):
    sc = MagicMock()
    sc.section_id = section_id
    sc.word_count = word_count
    sc.images = images or []
    sc.diagrams = diagrams or []
    return sc


def _patch_all_agents(
    chapters=None,
    curriculum=None,
    chapter_page_map=None,
    section_contents=None,
    html_path="/out/lecture_ko.html",
    quality_score=85.0,
    quality_passed=True,
):
    if chapters is None:
        chapters = [{"title": "Ch1", "start_page": 1, "end_page": 5, "raw_text": "x"}]
    if section_contents is None:
        section_contents = [_make_section_content()]
    if curriculum is None:
        curriculum = MagicMock()
        curriculum.sections = [MagicMock()]
        curriculum.total_estimated_time = 60
        curriculum.learning_objectives = ["obj1"]
    if chapter_page_map is None:
        chapter_page_map = {"s0": [1, 2, 3]}

    mock_translator = MagicMock()
    mock_translator.extract_structure.return_value = chapters
    mock_translator.build_curriculum.return_value = (curriculum, chapter_page_map)
    mock_translator.translate_chapters.return_value = section_contents
    mock_translator.assign_images_to_sections.return_value = section_contents

    mock_image_result = {"total_collected": 3, "images": []}
    mock_image_agent = MagicMock()
    mock_image_agent.collect.return_value = mock_image_result

    mock_html_assembler = MagicMock()
    mock_html_assembler.assemble.return_value = html_path

    mock_evaluation = MagicMock()
    mock_evaluation.overall_score = quality_score
    mock_evaluation.passed = quality_passed
    mock_evaluation.issues = []
    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = mock_evaluation

    mock_revision = MagicMock()
    mock_revision.revise.return_value = MagicMock()

    mock_lecture = MagicMock()
    mock_lecture.sections = section_contents
    mock_lecture.total_word_count = sum(s.word_count for s in section_contents)

    patches = [
        patch("lecture_forge.agents.pdf_translator.PDFTranslatorAgent",
              return_value=mock_translator),
        patch("lecture_forge.agents.image_collector.ImageCollectorAgent",
              return_value=mock_image_agent),
        patch("lecture_forge.agents.html_assembler.HTMLAssemblerAgent",
              return_value=mock_html_assembler),
        patch("lecture_forge.quality.evaluator.QualityEvaluator",
              return_value=mock_evaluator),
        patch("lecture_forge.agents.revision_agent.RevisionAgent",
              return_value=mock_revision),
        patch("lecture_forge.models.lecture.Lecture",
              return_value=mock_lecture),
    ]
    return patches, mock_translator, mock_image_agent, mock_html_assembler, mock_evaluator


class TestTranslateLecture:
    def _run(self, pdf_path, **kwargs):
        from lecture_forge.cli.commands.translate import translate_lecture
        patches, *_ = _patch_all_agents()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            return translate_lecture(pdf_path=pdf_path, **kwargs)

    def test_basic_return_keys(self, pdf_path):
        result = self._run(
            pdf_path,
            output_name=None,
            quality_level="balanced",
            audience_level="intermediate",
            with_slides=False,
            no_translate=False,
        )
        assert "html_path" in result
        assert "sections_count" in result
        assert "total_words" in result

    def test_no_translate_mode(self, pdf_path):
        result = self._run(
            pdf_path,
            output_name=None,
            quality_level="balanced",
            audience_level="intermediate",
            with_slides=False,
            no_translate=True,
        )
        assert result["html_path"] == "/out/lecture_ko.html"

    def test_with_diagrams(self, pdf_path):
        from lecture_forge.cli.commands.translate import translate_lecture
        sc = _make_section_content(diagrams=[MagicMock()])
        patches, translator, img_agent, html_asm, evaluator = _patch_all_agents(
            section_contents=[sc]
        )
        mock_diagram_gen = MagicMock()
        mock_diagram_gen.generate_diagrams.return_value = [sc]
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
             patch("lecture_forge.agents.diagram_generator.DiagramGeneratorAgent",
                   return_value=mock_diagram_gen):
            result = translate_lecture(
                pdf_path=pdf_path,
                output_name="out",
                quality_level="balanced",
                audience_level="intermediate",
                with_slides=False,
                no_translate=False,
                with_diagrams=True,
            )
        mock_diagram_gen.generate_diagrams.assert_called_once()

    def test_with_slides_success(self, pdf_path):
        from lecture_forge.cli.commands.translate import translate_lecture
        patches, *_ = _patch_all_agents()
        mock_converter = MagicMock()
        mock_converter.convert.return_value = True
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
             patch("lecture_forge.slides.SlideConverter",
                   return_value=mock_converter):
            result = translate_lecture(
                pdf_path=pdf_path,
                output_name=None,
                quality_level="balanced",
                audience_level="intermediate",
                with_slides=True,
                no_translate=False,
            )
        mock_converter.convert.assert_called_once()

    def test_with_slides_exception_handled(self, pdf_path):
        from lecture_forge.cli.commands.translate import translate_lecture
        patches, *_ = _patch_all_agents()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
             patch("lecture_forge.slides.SlideConverter",
                   side_effect=ImportError("no slides")):
            result = translate_lecture(
                pdf_path=pdf_path,
                output_name=None,
                quality_level="balanced",
                audience_level="intermediate",
                with_slides=True,
                no_translate=False,
            )
        assert "html_path" in result  # didn't crash

    def test_quality_passed_on_first_iter(self, pdf_path):
        from lecture_forge.cli.commands.translate import translate_lecture
        patches, translator, img_agent, html_asm, evaluator = _patch_all_agents(
            quality_passed=True
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = translate_lecture(
                pdf_path=pdf_path,
                output_name=None,
                quality_level="balanced",
                audience_level="intermediate",
                with_slides=False,
                no_translate=False,
            )
        assert result["quality_score"] == 85.0

    def test_quality_improvement_triggers_regen(self, pdf_path):
        from lecture_forge.cli.commands.translate import translate_lecture
        sc = _make_section_content()
        curriculum = MagicMock()
        curriculum.sections = [MagicMock()]
        curriculum.total_estimated_time = 60
        curriculum.learning_objectives = ["obj1"]

        mock_translator = MagicMock()
        mock_translator.extract_structure.return_value = [{}]
        mock_translator.build_curriculum.return_value = (curriculum, {})
        mock_translator.translate_chapters.return_value = [sc]
        mock_translator.assign_images_to_sections.return_value = [sc]

        mock_image_agent = MagicMock()
        mock_image_agent.collect.return_value = {"total_collected": 0, "images": []}

        mock_html_assembler = MagicMock()
        mock_html_assembler.assemble.return_value = "/out/lecture.html"

        # First eval fails, then revision improves it
        fail_eval = MagicMock()
        fail_eval.overall_score = 70.0
        fail_eval.passed = False
        fail_eval.issues = []

        improve_eval = MagicMock()
        improve_eval.overall_score = 85.0
        improve_eval.passed = False
        improve_eval.issues = []

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.side_effect = [fail_eval, improve_eval]

        revised_lecture = MagicMock()
        revised_lecture.sections = [sc]
        revised_lecture.total_word_count = 100

        mock_revision = MagicMock()
        mock_revision.revise.return_value = revised_lecture

        mock_lecture = MagicMock()
        mock_lecture.sections = [sc]
        mock_lecture.total_word_count = 100

        with patch("lecture_forge.agents.pdf_translator.PDFTranslatorAgent",
                   return_value=mock_translator), \
             patch("lecture_forge.agents.image_collector.ImageCollectorAgent",
                   return_value=mock_image_agent), \
             patch("lecture_forge.agents.html_assembler.HTMLAssemblerAgent",
                   return_value=mock_html_assembler), \
             patch("lecture_forge.quality.evaluator.QualityEvaluator",
                   return_value=mock_evaluator), \
             patch("lecture_forge.agents.revision_agent.RevisionAgent",
                   return_value=mock_revision), \
             patch("lecture_forge.models.lecture.Lecture",
                   return_value=mock_lecture), \
             patch("lecture_forge.config.Config") as mock_config:
            mock_config.MAX_ITERATIONS = 1
            result = translate_lecture(
                pdf_path=pdf_path,
                output_name=None,
                quality_level="balanced",
                audience_level="intermediate",
                with_slides=False,
                no_translate=False,
            )
        assert result is not None
