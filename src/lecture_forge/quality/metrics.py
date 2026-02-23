"""
Quality metrics for lecture evaluation.
"""

from typing import Dict

from lecture_forge.config import Config
from lecture_forge.constants import CodeComplexity, SectionBalance, WordCountExpected
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger


class QualityMetrics:
    """Quality metrics calculator."""

    def __init__(self):
        logger.info("Initializing quality metrics")

    def calculate_content_completeness(self, lecture: Lecture) -> float:
        """
        Calculate content completeness score.

        Args:
            lecture: Lecture to evaluate

        Returns:
            Score (0-100)
        """
        score = 0.0

        # 1. Check if learning objectives exist (10점)
        if lecture.learning_objectives:
            score += 10

        # 2. Check word count sufficiency (60점)
        if lecture.total_word_count > 0:
            # 예상: 250 words/minute reading speed
            expected_words = lecture.duration * Config.CONTENT_READING_WPM * Config.CONTENT_TIME_COVERAGE
            word_ratio = min(1.0, lecture.total_word_count / expected_words)
            score += 60 * word_ratio

        # 3. Check section coverage (30점)
        if len(lecture.sections) >= Config.CONTENT_MIN_SECTIONS:  # At least intro, content, conclusion
            score += 30

        return min(100.0, score)

    def calculate_logical_flow(self, lecture: Lecture) -> float:
        """
        Calculate logical flow score.

        Args:
            lecture: Lecture to evaluate

        Returns:
            Score (0-100)
        """
        score = 0.0

        # 1. Check for intro section (25점)
        if lecture.sections and "intro" in lecture.sections[0].section_id.lower():
            score += 25

        # 2. Check for conclusion section (25점)
        if lecture.sections and any(
            "conclusion" in s.section_id.lower() or "summary" in s.section_id.lower() for s in lecture.sections
        ):
            score += 25

        # 3. Check section balance (25점)
        if len(lecture.sections) >= Config.CONTENT_MIN_SECTIONS:
            # Sections should not be too unbalanced
            word_counts = [s.word_count for s in lecture.sections if s.word_count > 0]
            if word_counts:
                avg_words = sum(word_counts) / len(word_counts)
                # Check if most sections are within SectionBalance.TOLERANCE of average
                balanced = sum(1 for wc in word_counts if abs(wc - avg_words) / avg_words < SectionBalance.TOLERANCE)
                balance_ratio = balanced / len(word_counts)
                score += 25 * balance_ratio

        # 4. Check logical progression (25점)
        # Simple heuristic: difficulty should generally increase
        if len(lecture.sections) >= Config.CONTENT_MIN_SECTIONS:
            difficulty_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
            # Just check that we don't have advanced before beginner
            has_logical_order = True
            for i in range(len(lecture.sections) - 1):
                curr_diff = difficulty_map.get(lecture.sections[i].difficulty_level, 2)
                next_diff = difficulty_map.get(lecture.sections[i + 1].difficulty_level, 2)
                # Allow same or increasing difficulty
                if next_diff < curr_diff - 1:  # Significant jump backwards
                    has_logical_order = False
                    break
            if has_logical_order:
                score += 25

        return min(100.0, score)

    def calculate_time_alignment(self, lecture: Lecture) -> float:
        """
        Calculate time alignment score.

        Args:
            lecture: Lecture to evaluate

        Returns:
            Score (0-100)
        """
        score = 0.0

        # 1. Check overall content vs time (60점)
        # 250 words/min reading speed, but lecture has discussion/exercises
        # So expect 150-200 words per minute of lecture time
        expected_words_min = lecture.duration * Config.CONTENT_WPM_MIN
        expected_words_max = lecture.duration * Config.CONTENT_WPM_MAX

        if expected_words_min <= lecture.total_word_count <= expected_words_max:
            score += 60
        elif lecture.total_word_count > 0:
            # Penalize if too far from range
            if lecture.total_word_count < expected_words_min:
                ratio = lecture.total_word_count / expected_words_min
            else:
                ratio = expected_words_max / lecture.total_word_count
            score += 60 * ratio

        # 2. Check section time balance (40점)
        if len(lecture.sections) >= Config.CONTENT_MIN_SECTIONS:
            # Get word counts per section
            section_words = [s.word_count for s in lecture.sections if s.word_count > 0]
            if section_words:
                avg_words = sum(section_words) / len(section_words)
                # Check variance - sections shouldn't be too different
                # Allow SectionBalance.MAX_RATIO x variation
                balanced_sections = sum(
                    1 for wc in section_words
                    if SectionBalance.MIN_RATIO * avg_words <= wc <= SectionBalance.MAX_RATIO * avg_words
                )
                balance_ratio = balanced_sections / len(section_words)
                score += 40 * balance_ratio

        return min(100.0, score)

    def calculate_level_appropriateness(self, lecture: Lecture) -> float:
        """
        Calculate level appropriateness score.

        Args:
            lecture: Lecture to evaluate

        Returns:
            Score (0-100)
        """
        score = 0.0

        # 1. Check if sections have difficulty levels set (30점)
        sections_with_difficulty = sum(1 for s in lecture.sections if hasattr(s, "difficulty_level") and s.difficulty_level)
        if lecture.sections:
            score += 30 * (sections_with_difficulty / len(lecture.sections))

        # 2. Check word count per section matches level (40점)
        # Beginner needs more explanation, Advanced can be more concise
        appropriate_sections = 0
        for section in lecture.sections:
            if section.word_count == 0:
                continue

            section_level = getattr(section, "difficulty_level", lecture.audience_level)
            expected = WordCountExpected.BY_LEVEL.get(section_level, WordCountExpected.BY_LEVEL["intermediate"])

            if WordCountExpected.VARIATION_MIN * expected <= section.word_count <= WordCountExpected.VARIATION_MAX * expected:
                appropriate_sections += 1

        if lecture.sections:
            score += 40 * (appropriate_sections / len(lecture.sections))

        # 3. Check code complexity matches level (30점)
        total_code_lines = 0
        for section in lecture.sections:
            for code_block in section.code_blocks:
                total_code_lines += len(code_block.code.split("\n"))

        # Beginner: simpler code (fewer lines per example)
        # Advanced: more complex code (more lines per example)
        total_code_blocks = sum(len(s.code_blocks) for s in lecture.sections)
        if total_code_blocks > 0:
            avg_lines = total_code_lines / total_code_blocks

            if lecture.audience_level == "beginner" and avg_lines <= CodeComplexity.BEGINNER_MAX:
                score += 30
            elif lecture.audience_level == "intermediate" and CodeComplexity.INTERMEDIATE_MIN <= avg_lines <= CodeComplexity.INTERMEDIATE_MAX:
                score += 30
            elif lecture.audience_level == "advanced" and avg_lines >= CodeComplexity.ADVANCED_MIN:
                score += 30
            else:
                # Partial credit based on closeness
                score += 15

        return min(100.0, score)

    def calculate_visual_quality(self, lecture: Lecture) -> float:
        """
        Calculate visual quality score.

        Args:
            lecture: Lecture to evaluate

        Returns:
            Score (0-100)
        """
        score = 0.0

        # 1. Check diagram count (50점)
        # Expect at least 1 diagram per 2 sections
        expected_diagrams = max(1, len(lecture.sections) // 2)
        if lecture.total_diagrams >= expected_diagrams:
            score += 50
        else:
            score += 50 * (lecture.total_diagrams / expected_diagrams)

        # 2. Check image count (30점)
        # Expect at least 1 image per 20 minutes of lecture
        expected_images = max(1, lecture.duration // 20)
        if lecture.total_images >= expected_images:
            score += 30
        else:
            score += 30 * (lecture.total_images / expected_images)

        # 3. Check distribution (20점)
        # Visuals should be distributed across sections
        sections_with_visuals = sum(1 for s in lecture.sections if (len(s.diagrams) > 0 or len(s.images) > 0))

        if lecture.sections:
            # At least 50% of sections should have visuals
            distribution_ratio = sections_with_visuals / len(lecture.sections)
            score += 20 * min(1.0, distribution_ratio * 2)

        return min(100.0, score)

    def calculate_technical_accuracy(self, lecture: Lecture) -> float:
        """
        Calculate technical accuracy score.

        Args:
            lecture: Lecture to evaluate

        Returns:
            Score (0-100)
        """
        score = 0.0

        # 1. Basic syntax check for code blocks (50점)
        valid_code_blocks = 0
        total_code_blocks = 0

        for section in lecture.sections:
            for code_block in section.code_blocks:
                total_code_blocks += 1
                # Basic heuristics for code validity
                code = code_block.code.strip()

                if not code:
                    continue

                # Check for balanced brackets
                if code.count("{") == code.count("}") and code.count("(") == code.count(")"):
                    valid_code_blocks += 1

        if total_code_blocks > 0:
            score += 50 * (valid_code_blocks / total_code_blocks)
        else:
            # No code blocks, assume accurate
            score += 50

        # 2. Check for proper structure (50점)
        # - Has learning objectives
        # - Has proper sections
        # - Content is not empty
        structure_checks = 0

        if lecture.learning_objectives:
            structure_checks += 1

        if lecture.sections and len(lecture.sections) >= 3:
            structure_checks += 1

        if lecture.total_word_count > 1000:
            structure_checks += 1

        # Check that sections have titles
        if all(s.title for s in lecture.sections):
            structure_checks += 1

        score += 50 * (structure_checks / 4)

        return min(100.0, score)

    def calculate_all_metrics(self, lecture: Lecture) -> Dict[str, float]:
        """
        Calculate all quality metrics.

        Args:
            lecture: Lecture to evaluate

        Returns:
            Dictionary of metric scores
        """
        metrics = {
            "content_completeness": self.calculate_content_completeness(lecture),
            "logical_flow": self.calculate_logical_flow(lecture),
            "time_alignment": self.calculate_time_alignment(lecture),
            "level_appropriateness": self.calculate_level_appropriateness(lecture),
            "visual_quality": self.calculate_visual_quality(lecture),
            "technical_accuracy": self.calculate_technical_accuracy(lecture),
        }

        return metrics
