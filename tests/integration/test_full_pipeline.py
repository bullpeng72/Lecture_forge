"""
Integration tests for full lecture generation pipeline.

Tests the end-to-end flow: inputs → content collection → analysis →
curriculum design → content writing → diagrams → HTML output.
"""

import tempfile
from pathlib import Path

import pytest

from lecture_forge.agents.content_analyzer import ContentAnalyzerAgent
from lecture_forge.agents.content_collector import ContentCollectorAgent
from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.agents.curriculum_designer import CurriculumDesignerAgent
from lecture_forge.agents.diagram_generator import DiagramGeneratorAgent
from lecture_forge.agents.html_assembler import HTMLAssemblerAgent
from lecture_forge.agents.image_collector import ImageCollectorAgent
from lecture_forge.models.lecture import Lecture


@pytest.mark.integration
@pytest.mark.slow
class TestFullPipeline:
    """Test full lecture generation pipeline."""

    def test_minimal_pipeline_text_only(self):
        """
        Test minimal pipeline with text input only (no PDF, no images).

        This is the fastest integration test - useful for CI/CD.
        """
        # Arrange
        collection_name = "test_minimal_pipeline"
        topic = "Python Basics"

        # Phase 1: Content Collection (minimal - just keywords)
        content_agent = ContentCollectorAgent(collection_name=collection_name)
        content_result = content_agent.collect({
            "pdfs": [],
            "urls": [],
            "keywords": ["Python programming basics"],
            "hada_keywords": [],
        })

        assert content_result["success"] is True
        assert content_result["metadata"]["total_docs"] > 0

        # Phase 2: Skip image collection for speed
        image_result = {
            "success": True,
            "total_collected": 0,
            "images": [],
        }

        # Phase 3a: Content Analysis
        analyzer = ContentAnalyzerAgent(vector_store=content_agent.vector_store)
        analysis_result = analyzer.analyze(
            collection_result=content_result,
            image_result=image_result,
            topic=topic,
        )

        assert analysis_result is not None
        assert len(analysis_result.key_topics) > 0

        # Phase 3b: Curriculum Design
        designer = CurriculumDesignerAgent()
        curriculum = designer.design(
            analysis_result=analysis_result,
            topic=topic,
            duration=60,  # 1 hour
            audience_level="beginner",
        )

        assert curriculum is not None
        assert len(curriculum.sections) >= 3
        assert curriculum.total_estimated_time > 0

        # Phase 4a: Content Writing (simplified - just 1 section)
        writer = ContentWriterAgent(vector_store=content_agent.vector_store)
        first_section = curriculum.sections[0]
        section_content = writer.write_section(
            section=first_section,
            curriculum=curriculum,
            available_images=[],
        )

        assert section_content is not None
        assert section_content.title == first_section.title
        assert len(section_content.markdown_content) > 100  # Has substantial content

        # Phase 4b: Diagram Generation
        diagram_gen = DiagramGeneratorAgent()
        section_contents = diagram_gen.generate_diagrams([section_content])

        # Diagrams are optional (get first section back)
        section_content = section_contents[0]
        assert section_content.diagrams is not None

        # Phase 4c: HTML Assembly
        lecture = Lecture(
            title=f"{topic} - Beginner Level",
            topic=topic,
            duration=60,
            audience_level="beginner",
            learning_objectives=curriculum.learning_objectives,
            sections=[section_content],
            total_word_count=section_content.word_count,
            total_images=len(section_content.images),
            total_diagrams=len(section_content.diagrams),
            vector_db_path=str(content_agent.vector_store.db_path),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            html_assembler = HTMLAssemblerAgent()
            html_path = html_assembler.assemble(lecture, output_path=str(Path(tmpdir) / "test_lecture.html"))

            assert html_path is not None
            assert Path(html_path).exists()

            # Verify HTML content
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            assert topic in html_content
            assert section_content.title in html_content
            assert len(html_content) > 1000  # Non-trivial HTML

        # Cleanup - not needed, collections use unique names

    @pytest.mark.skip(reason="Requires actual PDF file and takes 5+ minutes")
    def test_full_pipeline_with_pdf(self):
        """
        Test full pipeline with actual PDF input.

        This is a comprehensive test but requires test fixtures and takes longer.
        Skip by default, run manually when needed.
        """
        # TODO: Implement when test fixtures are ready
        pass

    @pytest.mark.skip(reason="Requires network access and takes 5+ minutes")
    def test_full_pipeline_with_url(self):
        """
        Test full pipeline with URL scraping.

        Requires network access and external dependencies.
        """
        # TODO: Implement when needed
        pass
