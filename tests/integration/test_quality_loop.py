"""
Integration tests for quality evaluation and revision loop.

Tests the quality assurance system: evaluation → revision → re-evaluation.
"""

import pytest

from lecture_forge.config import Config
from lecture_forge.models.curriculum import Section
from lecture_forge.utils.content_metrics import calculate_target_metrics, evaluate_content_quality


@pytest.mark.integration
class TestQualityLoop:
    """Test quality evaluation and revision loop."""

    def test_quality_metrics_calculation(self):
        """
        Test target metrics calculation for different scenarios.

        Validates that metrics scale appropriately with duration and difficulty.
        """
        # Test beginner level (more words per minute)
        metrics_beginner = calculate_target_metrics(
            estimated_time=60,  # 60 minutes
            difficulty_level="beginner"
        )

        assert metrics_beginner["target_words"] > 0
        assert metrics_beginner["min_words"] == int(metrics_beginner["target_words"] * Config.MIN_WORDS_RATIO)
        assert metrics_beginner["max_words"] == int(metrics_beginner["target_words"] * Config.MAX_WORDS_RATIO)
        assert "target_practice_problems" in metrics_beginner

        # Test advanced level (different multiplier)
        metrics_advanced = calculate_target_metrics(
            estimated_time=60,
            difficulty_level="advanced"
        )

        # Advanced should have different targets
        assert metrics_advanced["target_words"] != metrics_beginner["target_words"]

    def test_quality_evaluation_meets_threshold(self):
        """
        Test quality evaluation for content that meets threshold.
        """
        # Create good quality content
        content = """
# Introduction to Python

Python is a high-level programming language known for its simplicity and readability.

## Key Features

Python offers several advantages:
- Easy to learn syntax
- Extensive standard library
- Cross-platform compatibility

## Code Example

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
```

## Practice Exercise

Write a function that calculates the factorial of a number.

## Summary

Python is an excellent choice for beginners and professionals alike.
""" * 20  # Repeat to meet word count (~1400 words for 10 min beginner)

        targets = calculate_target_metrics(estimated_time=10, difficulty_level="beginner")

        evaluation = evaluate_content_quality(
            content=content,
            targets=targets,
            image_count=3,        # Good number of images
        )

        assert evaluation["overall_score"] > 0
        assert "meets_requirements" in evaluation
        # With sufficient content, should meet basic requirements
        assert evaluation["word_count"] > targets["min_words"]

    def test_quality_evaluation_below_threshold(self):
        """
        Test quality evaluation for content below threshold.

        This should trigger revision in actual pipeline.
        """
        # Create minimal content (below threshold)
        content = """
# Short Section

This is too short.
"""

        targets = calculate_target_metrics(estimated_time=30, difficulty_level="beginner")

        evaluation = evaluate_content_quality(
            content=content,
            targets=targets,
            image_count=0,       # No images
        )

        assert evaluation["overall_score"] >= 0
        assert evaluation["word_count"] < targets["target_words"]
        # Low quality content should likely not meet requirements
        # (exact threshold depends on Config.QUALITY_THRESHOLD_SECTION)

    def test_section_quality_threshold_config(self):
        """
        Test that section-level threshold is properly configured.

        Validates that Config.QUALITY_THRESHOLD_SECTION is used
        instead of hardcoded values.
        """
        # This test validates that we're using Config
        assert hasattr(Config, "QUALITY_THRESHOLD_SECTION")
        assert isinstance(Config.QUALITY_THRESHOLD_SECTION, int)
        assert 0 <= Config.QUALITY_THRESHOLD_SECTION <= 100

        # Should be lower than overall threshold (more lenient)
        assert Config.QUALITY_THRESHOLD_SECTION <= Config.QUALITY_THRESHOLD

    @pytest.mark.skip(reason="Requires actual agent execution and takes time")
    def test_full_quality_revision_loop(self):
        """
        Test complete quality evaluation and revision cycle.

        This would test:
        1. Generate initial content
        2. Evaluate quality
        3. If below threshold, request revision
        4. Re-evaluate
        5. Verify improvement or max iterations reached

        Skipped by default as it requires full agent pipeline.
        """
        # TODO: Implement when needed for comprehensive testing
        pass
