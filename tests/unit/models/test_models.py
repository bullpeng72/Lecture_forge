"""
Unit tests for LectureForge data models.
"""

import pytest

from lecture_forge.models.analysis import (
    AnalysisResult,
    ConceptRelation,
    Entity,
    TopicCluster,
)
from lecture_forge.models.evaluation import EvaluationResult, Issue
from lecture_forge.models.lecture import (
    CodeBlock,
    ImageReference,
    Lecture,
    MermaidDiagram,
    SectionContent,
)


# ===== Analysis Models =====

class TestEntity:
    def test_creation(self):
        e = Entity(name="Python", type="technology", description="A programming language")
        assert e.name == "Python"
        assert e.mentions == 1
        assert e.difficulty == "intermediate"
        assert e.sources == []

    def test_with_all_fields(self):
        e = Entity(
            name="Decorator",
            type="concept",
            description="A design pattern",
            mentions=5,
            sources=["doc1.pdf", "doc2.pdf"],
            difficulty="advanced",
        )
        assert e.mentions == 5
        assert len(e.sources) == 2


class TestConceptRelation:
    def test_creation(self):
        r = ConceptRelation(source="Functions", target="Closures", relation_type="prerequisite")
        assert r.source == "Functions"
        assert r.target == "Closures"
        assert r.strength == 1.0


class TestTopicCluster:
    def test_creation(self):
        tc = TopicCluster(id="c1", name="Basics")
        assert tc.concepts == []
        assert tc.central_concept is None
        assert tc.difficulty == "intermediate"


class TestAnalysisResult:
    def test_empty_creation(self):
        ar = AnalysisResult()
        assert ar.entities == []
        assert ar.key_topics == []
        assert ar.topic_clusters == []
        assert ar.concept_relations == []

    def test_get_entities_by_type(self):
        ar = AnalysisResult(
            entities=[
                Entity(name="Python", type="technology", description="lang"),
                Entity(name="OOP", type="concept", description="paradigm"),
                Entity(name="Flask", type="technology", description="framework"),
            ]
        )
        tech = ar.get_entities_by_type("technology")
        assert len(tech) == 2
        assert all(e.type == "technology" for e in tech)

    def test_get_entities_by_type_no_match(self):
        ar = AnalysisResult(entities=[Entity(name="X", type="concept", description="y")])
        assert ar.get_entities_by_type("technology") == []

    def test_get_beginner_topics(self):
        ar = AnalysisResult(
            difficulty_scores={"Variables": 0.2, "Decorators": 0.8, "Loops": 0.1}
        )
        beginners = ar.get_beginner_topics()
        assert "Variables" in beginners
        assert "Loops" in beginners
        assert "Decorators" not in beginners

    def test_get_advanced_topics(self):
        ar = AnalysisResult(
            difficulty_scores={"Variables": 0.2, "Metaclasses": 0.9, "Asyncio": 0.85}
        )
        advanced = ar.get_advanced_topics()
        assert "Metaclasses" in advanced
        assert "Asyncio" in advanced
        assert "Variables" not in advanced

    def test_get_prerequisites(self):
        ar = AnalysisResult(
            concept_relations=[
                ConceptRelation(source="Functions", target="Closures", relation_type="prerequisite"),
                ConceptRelation(source="Classes", target="Closures", relation_type="related_to"),
            ]
        )
        prereqs = ar.get_prerequisites("Closures")
        assert prereqs == ["Functions"]

    def test_get_prerequisites_none(self):
        ar = AnalysisResult()
        assert ar.get_prerequisites("Closures") == []

    def test_get_related_topics(self):
        ar = AnalysisResult(
            concept_relations=[
                ConceptRelation(source="Functions", target="Closures", relation_type="related_to"),
                ConceptRelation(source="Closures", target="Decorators", relation_type="related_to"),
            ]
        )
        related = ar.get_related_topics("Closures")
        assert "Functions" in related
        assert "Decorators" in related

    def test_get_related_topics_deduplication(self):
        ar = AnalysisResult(
            concept_relations=[
                ConceptRelation(source="A", target="B", relation_type="related_to"),
                ConceptRelation(source="A", target="B", relation_type="related_to"),
            ]
        )
        related = ar.get_related_topics("A")
        assert len(related) == 1


# ===== Evaluation Models =====

class TestIssue:
    def test_creation(self):
        issue = Issue(
            dimension="content_completeness",
            severity="high",
            location="section_1",
            description="Not enough content",
            suggestion="Add more examples",
        )
        assert issue.dimension == "content_completeness"
        assert issue.severity == "high"


class TestEvaluationResult:
    def test_basic_creation(self):
        r = EvaluationResult(overall_score=85.0, passed=True)
        assert r.overall_score == 85.0
        assert r.passed is True
        assert r.dimension_scores == {}
        assert r.issues == []
        assert r.revision_strategy == "none"
        assert r.iteration == 0

    def test_is_auto_fixable_high_score(self):
        r = EvaluationResult(overall_score=75.0, passed=False)
        assert r.is_auto_fixable() is True

    def test_is_auto_fixable_low_score(self):
        r = EvaluationResult(overall_score=55.0, passed=False)
        assert r.is_auto_fixable() is False

    def test_is_auto_fixable_too_many_high_issues(self):
        issues = [
            Issue(dimension="d", severity="high", location="g", description="x", suggestion="y")
            for _ in range(4)
        ]
        r = EvaluationResult(overall_score=75.0, passed=False, issues=issues)
        assert r.is_auto_fixable() is False

    def test_is_auto_fixable_few_high_issues(self):
        issues = [
            Issue(dimension="d", severity="high", location="g", description="x", suggestion="y")
            for _ in range(2)
        ]
        r = EvaluationResult(overall_score=75.0, passed=False, issues=issues)
        assert r.is_auto_fixable() is True

    def test_get_quality_level_excellent(self):
        r = EvaluationResult(overall_score=92.0, passed=True)
        assert r.get_quality_level() == "Excellent"

    def test_get_quality_level_good(self):
        r = EvaluationResult(overall_score=85.0, passed=True)
        assert r.get_quality_level() == "Good"

    def test_get_quality_level_fair(self):
        r = EvaluationResult(overall_score=72.0, passed=False)
        assert r.get_quality_level() == "Fair"

    def test_get_quality_level_poor(self):
        r = EvaluationResult(overall_score=62.0, passed=False)
        assert r.get_quality_level() == "Poor"

    def test_get_quality_level_needs_revision(self):
        r = EvaluationResult(overall_score=45.0, passed=False)
        assert r.get_quality_level() == "Needs Major Revision"


# ===== Lecture Models =====

class TestCodeBlock:
    def test_creation(self):
        cb = CodeBlock(language="python", code="print('hello')")
        assert cb.language == "python"
        assert cb.caption is None


class TestImageReference:
    def test_creation(self):
        ir = ImageReference(image_id="img1", path="/tmp/img.png", description="A diagram")
        assert ir.image_id == "img1"
        assert ir.caption is None
        assert ir.attribution is None


class TestMermaidDiagram:
    def test_creation(self):
        d = MermaidDiagram(
            id="d1",
            title="Flow",
            mermaid_code="flowchart TD\n  A --> B",
            diagram_type="flowchart",
        )
        assert d.id == "d1"
        assert d.diagram_type == "flowchart"


class TestSectionContent:
    def test_creation(self):
        sc = SectionContent(
            section_id="s1",
            title="Introduction",
            markdown_content="# Intro\n\nHello world.",
        )
        assert sc.section_id == "s1"
        assert sc.word_count == 0
        assert sc.estimated_time == 20
        assert sc.difficulty_level == "intermediate"
        assert sc.code_blocks == []
        assert sc.images == []
        assert sc.diagrams == []


class TestLecture:
    def _make_lecture(self):
        s1 = SectionContent(
            section_id="s1", title="Intro", markdown_content="Introduction text here."
        )
        s2 = SectionContent(
            section_id="s2", title="Advanced", markdown_content="Advanced content here."
        )
        return Lecture(
            title="Python Basics",
            topic="Python",
            duration=60,
            audience_level="beginner",
            learning_objectives=["Learn Python"],
            sections=[s1, s2],
        )

    def test_creation(self):
        lec = self._make_lecture()
        assert lec.title == "Python Basics"
        assert len(lec.sections) == 2
        assert lec.total_word_count == 0

    def test_to_text(self):
        lec = self._make_lecture()
        text = lec.to_text()
        assert "Python Basics" in text
        assert "Intro" in text
        assert "Advanced" in text
        assert "Introduction text here." in text

    def test_to_text_empty_sections(self):
        lec = Lecture(title="Empty", topic="T", duration=30, audience_level="beginner")
        text = lec.to_text()
        assert "Empty" in text

    def test_get_section_found(self):
        lec = self._make_lecture()
        sec = lec.get_section("s1")
        assert sec is not None
        assert sec.title == "Intro"

    def test_get_section_not_found(self):
        lec = self._make_lecture()
        assert lec.get_section("nonexistent") is None

    def test_update_section(self):
        lec = self._make_lecture()
        new_sec = SectionContent(
            section_id="s1", title="Updated Intro", markdown_content="Updated content."
        )
        lec.update_section("s1", new_sec)
        assert lec.get_section("s1").title == "Updated Intro"

    def test_update_section_not_found(self):
        """update_section with non-existent ID should be a no-op."""
        lec = self._make_lecture()
        new_sec = SectionContent(
            section_id="s99", title="Ghost", markdown_content="Ghost content."
        )
        lec.update_section("s99", new_sec)
        # Original sections unchanged
        assert len(lec.sections) == 2
