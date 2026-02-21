"""
Integration tests for refactored ContentWriter components.

Tests the interaction between:
- ContentWriterAgent (main orchestrator)
- ImageSelector (image selection logic)
- CodeGenerator (code extraction/generation)
- ContentExpander (quality improvement)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from lecture_forge.agents.content_writer import ContentWriterAgent
from lecture_forge.agents.content_writer.image_selector import ImageSelector
from lecture_forge.agents.content_writer.code_generator import CodeGenerator
from lecture_forge.agents.content_writer.content_expander import ContentExpander
from lecture_forge.models.curriculum import Curriculum, Section
from lecture_forge.models.lecture import ImageReference, CodeBlock


class TestContentWriterIntegration:
    """Test ContentWriterAgent with all components."""

    def test_agent_initialization(self):
        """Test that agent initializes all components correctly."""
        agent = ContentWriterAgent()

        assert hasattr(agent, 'image_selector')
        assert hasattr(agent, 'code_generator')
        assert hasattr(agent, 'content_expander')
        assert isinstance(agent.image_selector, ImageSelector)
        assert isinstance(agent.code_generator, CodeGenerator)
        assert isinstance(agent.content_expander, ContentExpander)

    def test_image_selector_integration(self):
        """Test ImageSelector receives keyword_expander from agent."""
        agent = ContentWriterAgent()

        # Verify ImageSelector can use the keyword expansion
        assert agent.image_selector._expand_keywords is not None

        # Test keyword expansion
        keywords = agent.image_selector._expand_keywords("machine learning", {})
        assert isinstance(keywords, list)
        assert len(keywords) > 0

    def test_components_receive_llm_client(self):
        """Test that components receive LLM client from agent."""
        mock_vector_store = Mock()
        agent = ContentWriterAgent(vector_store=mock_vector_store)

        # Verify components have access to LLM and vector store
        assert agent.code_generator.llm is not None
        assert agent.code_generator.vector_store == mock_vector_store
        assert agent.content_expander.llm is not None
        assert agent.content_expander.vector_store == mock_vector_store

    @patch('lecture_forge.agents.content_writer.agent.ContentWriterAgent._query_knowledge')
    @patch('lecture_forge.agents.content_writer.agent.ContentWriterAgent._generate_content')
    def test_write_section_calls_all_components(self, mock_generate, mock_query):
        """Test that write_section orchestrates all components."""
        # Setup
        agent = ContentWriterAgent()
        mock_vector_store = Mock()
        agent.vector_store = mock_vector_store

        # Mock responses
        mock_query.return_value = (["context1", "context2"], [{"source": "test.pdf", "page_number": 1}])
        mock_generate.return_value = "# Test Content\n\n```python\nprint('hello')\n```\n\nSome text."

        section = Section(
            id="s1",
            title="Test Section",
            topics=["topic1", "topic2"],
            learning_objectives=["objective1"],
            estimated_time=30,
            difficulty_level="intermediate",
        )
        curriculum = Curriculum(
            topic="Test Topic",
            duration=60,
            audience_level="beginner",
            sections=[section],
        )

        # Execute
        with patch.object(agent.image_selector, 'select_images', return_value=[]):
            result = agent.write_section(section, curriculum, available_images=[])

        # Verify orchestration
        assert mock_query.called
        assert mock_generate.called
        assert result is not None


class TestImageSelectorIntegration:
    """Test ImageSelector component integration."""

    def test_image_selection_with_location_matching(self):
        """Test location-based image matching."""
        selector = ImageSelector()

        # Mock data
        section = Section(
            id="s1",
            title="Machine Learning Basics",
            topics=["supervised learning", "neural networks"],
            learning_objectives=["Understand ML concepts"],
            estimated_time=30,
            difficulty_level="intermediate",
        )

        available_images = [
            {
                "id": "img1",
                "path": "/test/img1.png",
                "source": "ml_book.pdf",
                "page": 5,
                "description": "Neural network diagram",
            },
            {
                "id": "img2",
                "path": "/test/img2.png",
                "source": "ml_book.pdf",
                "page": 10,
                "description": "Supervised learning flowchart",
            },
        ]

        context_metadatas = [
            {"source": "ml_book.pdf", "page_number": 5},
            {"source": "ml_book.pdf", "page_number": 5},
            {"source": "ml_book.pdf", "page_number": 10},
        ]

        # Execute
        with patch.object(selector, '_load_image_page_map', return_value={}):
            selected = selector.select_images(section, available_images, context_metadatas)

        # Images should be selected (even if location matching fails, fallback works)
        assert isinstance(selected, list)

    def test_image_quality_scoring(self):
        """Test image quality evaluation."""
        selector = ImageSelector()

        good_image = {
            "id": "good",
            "width": 800,
            "height": 600,
            "file_size": 100000,
            "content_type": "diagram",
        }

        bad_image = {
            "id": "bad",
            "width": 100,
            "height": 100,
            "file_size": 5000,
            "content_type": "photo",
        }

        good_score = selector._evaluate_image_quality_simple(good_image)
        bad_score = selector._evaluate_image_quality_simple(bad_image)

        # Good image should score higher
        assert good_score > bad_score
        assert good_score >= 0.0
        assert good_score <= 1.0


class TestCodeGeneratorIntegration:
    """Test CodeGenerator component integration."""

    def test_extract_code_blocks(self):
        """Test code block extraction from markdown."""
        generator = CodeGenerator()

        markdown = """
# Section Title

Some text here.

```python
def hello():
    print("Hello, World!")
```

More text.

```javascript
console.log("Hello");
```
"""

        blocks = generator.extract_code_blocks(markdown)

        assert len(blocks) == 2
        assert blocks[0].language == "python"
        assert blocks[1].language == "javascript"
        assert "Hello, World!" in blocks[0].code

    def test_generate_code_examples_with_context(self):
        """Test code generation with RAG context."""
        mock_vector_store = Mock()
        generator = CodeGenerator(vector_store=mock_vector_store)

        section = Section(
            id="s1",
            title="Python Basics",
            topics=["variables", "functions"],
            learning_objectives=["Learn Python"],
            estimated_time=30,
            difficulty_level="beginner",
        )
        curriculum = Curriculum(
            topic="Programming",
            duration=60,
            audience_level="beginner",
            sections=[section],
        )

        contexts = ["Python is a programming language", "Functions are reusable code"]

        with patch.object(generator, 'invoke_llm', return_value=Mock(content="```python\nprint('test')\n```")):
            result = generator.generate_code_examples(section, curriculum, contexts, num_examples=2)

        assert isinstance(result, str)
        assert len(result) > 0


class TestContentExpanderIntegration:
    """Test ContentExpander component integration."""

    def test_count_images_in_markdown(self):
        """Test image counting in markdown."""
        expander = ContentExpander()

        markdown = """
# Title

![Image 1](path/to/img1.png)

Some text.

![Image 2](path/to/img2.png)

![Image 3](path/to/img3.png)
"""

        count = expander.count_images(markdown)
        assert count == 3

    def test_expand_content_improves_quality(self):
        """Test content expansion improves quality metrics."""
        expander = ContentExpander()

        section = Section(
            id="s1",
            title="Test",
            topics=["topic"],
            learning_objectives=["Learn"],
            estimated_time=30,
            difficulty_level="intermediate",
        )
        curriculum = Curriculum(topic="Test", duration=60, audience_level="beginner", sections=[section])

        short_content = "Short content."
        contexts = ["Context 1", "Context 2"]
        targets = {"min_words": 500, "target_words": 800, "min_code_examples": 1, "min_subsections": 2}
        previous_quality = {"word_count": 2, "score": 40, "code_block_count": 0, "subsection_count": 0}

        expanded_content = "# Expanded Content\n\nThis is much longer content with more detail and examples."
        with patch.object(expander, 'invoke_llm', return_value=Mock(content=expanded_content)):
            expanded = expander.expand_content(
                section=section,
                curriculum=curriculum,
                contexts=contexts,
                targets=targets,
                previous_content=short_content,
                previous_quality=previous_quality,
            )

        assert isinstance(expanded, str)


class TestEndToEndWorkflow:
    """Test complete content generation workflow."""

    @patch('lecture_forge.agents.content_writer.agent.ContentWriterAgent._query_knowledge')
    @patch('lecture_forge.agents.content_writer.agent.ContentWriterAgent._generate_content')
    def test_full_section_generation_workflow(self, mock_generate, mock_query):
        """Test complete workflow from curriculum to section content."""
        # Setup agent with all components
        agent = ContentWriterAgent()

        # Mock RAG and LLM
        mock_query.return_value = (
            ["Context about machine learning", "More ML context"],
            [{"source": "ml.pdf", "page_number": 1}],
        )
        mock_generate.return_value = """
# Machine Learning Introduction

Machine learning is a subset of artificial intelligence.

```python
import numpy as np
def train_model(data):
    return model
```

![ML Diagram](ml_diagram.png)
"""

        # Create curriculum
        section = Section(
            id="s1",
            title="Introduction to ML",
            topics=["machine learning", "AI"],
            learning_objectives=["Understand ML basics"],
            estimated_time=30,
            difficulty_level="beginner",
        )
        curriculum = Curriculum(
            topic="Machine Learning",
            duration=60,
            audience_level="beginner",
            sections=[section],
        )

        # Mock images
        available_images = [
            {
                "id": "img1",
                "path": "/test/ml_diagram.png",
                "description": "Machine learning workflow",
                "source": "web",
            }
        ]

        # Execute full workflow
        with patch.object(agent.image_selector, 'select_images') as mock_select:
            mock_select.return_value = [
                ImageReference(
                    image_id="img1",
                    path="/test/ml_diagram.png",
                    description="ML diagram",
                    caption="Machine learning workflow",
                )
            ]

            result = agent.write_section(section, curriculum, available_images)

        # Verify complete pipeline execution
        assert result is not None
        assert mock_query.called
        assert mock_generate.called
        assert len(result.images) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
