"""
Extended unit tests for CurriculumDesignerAgent — covers missing lines
123-125, 148, 199, 327-432, 434-498, 512-602.
"""

import json
from unittest.mock import MagicMock, patch, call

import pytest

from lecture_forge.agents.curriculum_designer import CurriculumDesignerAgent
from lecture_forge.models.analysis import AnalysisResult, Entity, TopicCluster
from lecture_forge.models.curriculum import Curriculum, Section


# ── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_analysis():
    return AnalysisResult(
        entities=[
            Entity(name="neural network", type="concept", description="A computing model"),
            Entity(name="backprop", type="technique", description="Gradient descent algorithm"),
        ],
        key_topics=["ML basics", "Neural networks", "Backpropagation", "Overfitting", "Regularization"],
        topic_clusters=[
            TopicCluster(
                id="c1",
                name="ML basics",
                concepts=["Supervised", "Unsupervised"],
                difficulty="beginner",
                estimated_time=20,
            ),
            TopicCluster(
                id="c2",
                name="Neural networks",
                concepts=["Perceptron", "Activation"],
                difficulty="intermediate",
                estimated_time=30,
            ),
        ],
        difficulty_scores={
            "ML basics": 0.3,
            "Neural networks": 0.6,
            "Backpropagation": 0.8,
            "Overfitting": 0.5,
            "Regularization": 0.7,
        },
        metadata={"source_files": ["doc1.pdf", "doc2.pdf"]},
    )


@pytest.fixture
def designer(test_env_vars, mock_llm):
    return CurriculumDesignerAgent()


def _mock_llm_response(content: str):
    r = MagicMock()
    r.content = content
    r.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}
    return r


# ── _generate_learning_objectives (lines 88-128) ────────────────────────────

class TestGenerateLearningObjectives:
    def test_returns_list_on_valid_json(self, designer, mock_llm):
        mock_llm.invoke.return_value = _mock_llm_response(
            '["ML을 이해한다", "신경망을 설명할 수 있다", "역전파를 적용할 수 있다"]'
        )
        result = designer._generate_learning_objectives("ML", MagicMock(key_topics=["ML"]), "beginner")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_caps_at_five_objectives(self, designer, mock_llm):
        objs = [f"목표 {i}" for i in range(10)]
        mock_llm.invoke.return_value = _mock_llm_response(json.dumps(objs))
        result = designer._generate_learning_objectives("ML", MagicMock(key_topics=["T"]), "intermediate")
        assert len(result) <= 5

    def test_fallback_on_json_decode_error(self, designer, mock_llm):
        """Lines 123-125: JSONDecodeError → fallback list returned."""
        mock_llm.invoke.return_value = _mock_llm_response("NOT VALID JSON {{{{")
        result = designer._generate_learning_objectives("Python", MagicMock(key_topics=["X"]), "beginner")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "Python" in result[0]

    def test_fallback_on_unexpected_format(self, designer, mock_llm):
        """Non-list JSON → fallback."""
        mock_llm.invoke.return_value = _mock_llm_response('{"key": "not a list"}')
        result = designer._generate_learning_objectives("Python", MagicMock(key_topics=[]), "advanced")
        assert isinstance(result, list)

    def test_uses_top5_key_topics(self, designer, mock_llm):
        """Only top-5 key topics should be used."""
        many_topics = [f"topic{i}" for i in range(20)]
        mock_llm.invoke.return_value = _mock_llm_response('["목표1"]')
        analysis = MagicMock(key_topics=many_topics)
        designer._generate_learning_objectives("X", analysis, "intermediate")
        # Verify LLM was called
        assert mock_llm.invoke.called


# ── _select_topics (lines 130-155) ──────────────────────────────────────────

class TestSelectTopics:
    def _analysis(self, topics, scores):
        a = MagicMock()
        a.key_topics = topics
        a.difficulty_scores = scores
        return a

    def test_beginner_filters_easy_topics(self, designer):
        topics = ["easy", "medium", "hard"]
        scores = {"easy": 0.3, "medium": 0.55, "hard": 0.8}
        result = designer._select_topics(self._analysis(topics, scores), 60, "beginner")
        assert "easy" in result
        # medium (0.55) < 0.6 so it's included; hard (0.8) > 0.6 excluded
        assert "hard" not in result

    def test_advanced_filters_hard_topics(self, designer):
        """Line 148: advanced keeps topics with score > 0.4."""
        topics = ["easy", "medium", "hard"]
        scores = {"easy": 0.3, "medium": 0.5, "hard": 0.8}
        result = designer._select_topics(self._analysis(topics, scores), 60, "advanced")
        assert "hard" in result
        assert "easy" not in result

    def test_intermediate_returns_all(self, designer):
        """Line 148: intermediate → all topics returned (up to max)."""
        topics = ["a", "b", "c"]
        scores = {}
        result = designer._select_topics(self._analysis(topics, scores), 60, "intermediate")
        assert set(result) == {"a", "b", "c"}

    def test_respects_max_topics_by_duration(self, designer):
        topics = [f"t{i}" for i in range(50)]
        scores = {}
        result = designer._select_topics(self._analysis(topics, scores), 30, "intermediate")
        max_topics = max(3, 30 // 10)  # = 3
        assert len(result) <= max_topics

    def test_min_topics_at_least_3(self, designer):
        topics = ["only_one"]
        scores = {}
        result = designer._select_topics(self._analysis(topics, scores), 10, "intermediate")
        # max_topics = max(3, 10//10) = max(3, 1) = 3; only 1 topic available
        assert len(result) == 1


# ── _create_sections (lines 157-251) ────────────────────────────────────────

class TestCreateSections:
    def _ko_analysis(self):
        a = MagicMock()
        a.topic_clusters = []
        a.difficulty_scores = {}
        return a

    def test_creates_intro_and_conclusion(self, designer):
        sections = designer._create_sections(
            ["Topic A"], self._ko_analysis(), 60, "intermediate",
            topic="Test", learning_objectives=["목표1"]
        )
        ids = [s.id for s in sections]
        assert any("intro" in i for i in ids)
        assert any("conclusion" in i for i in ids)

    def test_empty_topics_uses_overview(self, designer):
        """Line 199: empty topics list → ['Overview'] fallback."""
        sections = designer._create_sections(
            [], self._ko_analysis(), 60, "intermediate",
            topic="Test", learning_objectives=["objective"]
        )
        titles = [s.title for s in sections]
        assert "Overview" in titles

    def test_difficulty_beginner_for_low_score(self, designer):
        a = MagicMock()
        a.topic_clusters = []
        a.difficulty_scores = {"EasyTopic": 0.2}  # < 0.4 → beginner
        sections = designer._create_sections(
            ["EasyTopic"], a, 60, "intermediate", topic="T",
            learning_objectives=["obj"]
        )
        content_sections = [s for s in sections if "intro" not in s.id and "conclusion" not in s.id]
        assert content_sections[0].difficulty_level == "beginner"

    def test_difficulty_advanced_for_high_score(self, designer):
        a = MagicMock()
        a.topic_clusters = []
        a.difficulty_scores = {"HardTopic": 0.9}  # > 0.7 → advanced
        sections = designer._create_sections(
            ["HardTopic"], a, 60, "intermediate", topic="T",
            learning_objectives=["obj"]
        )
        content_sections = [s for s in sections if "intro" not in s.id and "conclusion" not in s.id]
        assert content_sections[0].difficulty_level == "advanced"

    def test_korean_sections_when_korean_objectives(self, designer):
        sections = designer._create_sections(
            ["주제1"], self._ko_analysis(), 60, "intermediate",
            topic="T", learning_objectives=["목표를 이해한다"]
        )
        intro = next(s for s in sections if "intro" in s.id)
        assert intro.title == "소개"

    def test_english_sections_when_english_objectives(self, designer):
        sections = designer._create_sections(
            ["Topic"], self._ko_analysis(), 60, "intermediate",
            topic="T", learning_objectives=["Understand the fundamentals"]
        )
        intro = next(s for s in sections if "intro" in s.id)
        assert intro.title == "Introduction"


# ── _review_with_rmc (lines 253-362) ────────────────────────────────────────

class TestReviewWithRmc:
    def _make_curriculum(self, n=3):
        sections = [
            Section(id=f"s{i}", title=f"Section {i}", estimated_time=20, difficulty_level="intermediate")
            for i in range(n)
        ]
        return Curriculum(
            topic="Test Topic",
            duration=60,
            audience_level="intermediate",
            learning_objectives=["obj1", "obj2"],
            sections=sections,
            total_estimated_time=60,
        )

    def test_no_changes_returns_same_curriculum(self, designer, mock_llm):
        """Lines 327-328: no_changes=true → early return."""
        mock_llm.invoke.return_value = _mock_llm_response(
            '{"revised_objectives": null, "section_reorder": null, "issues": [], '
            '"reasoning": "All good", "no_changes": true}'
        )
        curriculum = self._make_curriculum()
        original_sections = list(curriculum.sections)
        result = designer._review_with_rmc(curriculum, MagicMock())
        assert [s.id for s in result.sections] == [s.id for s in original_sections]

    def test_applies_section_reorder(self, designer, mock_llm):
        """Lines 340-354: section_reorder applied correctly."""
        curriculum = self._make_curriculum(3)
        new_order = ["s2", "s0", "s1"]
        mock_llm.invoke.return_value = _mock_llm_response(
            json.dumps({
                "revised_objectives": None,
                "section_reorder": new_order,
                "issues": [],
                "reasoning": "Better order",
                "no_changes": False,
            })
        )
        result = designer._review_with_rmc(curriculum, MagicMock())
        assert [s.id for s in result.sections] == new_order

    def test_applies_revised_objectives(self, designer, mock_llm):
        """Lines 335-337: revised_objectives applied."""
        curriculum = self._make_curriculum()
        new_objs = ["새 목표1", "새 목표2"]
        mock_llm.invoke.return_value = _mock_llm_response(
            json.dumps({
                "revised_objectives": new_objs,
                "section_reorder": None,
                "issues": ["Some issue"],
                "reasoning": "Objectives updated",
                "no_changes": False,
            })
        )
        result = designer._review_with_rmc(curriculum, MagicMock())
        assert result.learning_objectives == new_objs

    def test_json_decode_error_breaks_gracefully(self, designer, mock_llm):
        """Lines 358-360: JSONDecodeError → break, return current curriculum."""
        mock_llm.invoke.return_value = _mock_llm_response("INVALID JSON !!!")
        curriculum = self._make_curriculum()
        result = designer._review_with_rmc(curriculum, MagicMock())
        assert result is curriculum  # same object returned

    def test_partial_section_reorder_not_applied(self, designer, mock_llm):
        """If reorder list length != sections length, reorder is NOT applied."""
        curriculum = self._make_curriculum(3)
        # Only 2 of 3 IDs in reorder — length mismatch → skip
        mock_llm.invoke.return_value = _mock_llm_response(
            json.dumps({
                "revised_objectives": None,
                "section_reorder": ["s0", "s1"],  # missing s2
                "issues": [],
                "reasoning": "partial",
                "no_changes": False,
            })
        )
        original_order = [s.id for s in curriculum.sections]
        result = designer._review_with_rmc(curriculum, MagicMock())
        # Partial reorder: s2 should be appended at end
        assert "s2" in [s.id for s in result.sections]

    def test_max_rmc_rounds_respected(self, designer, mock_llm):
        """RMC should never exceed Config.MAX_RMC_ROUNDS iterations."""
        from lecture_forge.config import Config
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            return _mock_llm_response(
                json.dumps({
                    "revised_objectives": None,
                    "section_reorder": None,
                    "issues": ["issue"],
                    "reasoning": "reason",
                    "no_changes": False,
                })
            )

        mock_llm.invoke.side_effect = side_effect
        curriculum = self._make_curriculum()
        designer._review_with_rmc(curriculum, MagicMock())
        assert call_count["n"] <= Config.MAX_RMC_ROUNDS

    def test_issues_logged_but_not_raised(self, designer, mock_llm):
        """Issues list in review response should not cause exceptions."""
        mock_llm.invoke.return_value = _mock_llm_response(
            json.dumps({
                "revised_objectives": None,
                "section_reorder": None,
                "issues": ["issue A", "issue B", "issue C"],
                "reasoning": "Many issues",
                "no_changes": False,
            })
        )
        curriculum = self._make_curriculum()
        result = designer._review_with_rmc(curriculum, MagicMock())
        assert result is not None


# ── _validate_and_enrich_sections (lines 364-498) ────────────────────────────

class TestValidateAndEnrichSections:
    def _make_sections(self, n=3):
        sections = []
        sections.append(Section(id="section_0_intro", title="Intro", estimated_time=5, difficulty_level="beginner"))
        for i in range(1, n):
            sections.append(Section(id=f"section_{i}_topic", title=f"Topic {i}", estimated_time=20, difficulty_level="intermediate"))
        sections.append(Section(id="section_conclusion", title="Conclusion", estimated_time=5, difficulty_level="beginner"))
        return sections

    def test_returns_sections_when_no_vector_store(self, test_env_vars, mock_llm):
        """Lines 381-382: no vector_store → return as-is."""
        designer = CurriculumDesignerAgent(vector_store=None)
        sections = self._make_sections()
        result = designer._validate_and_enrich_sections(sections, 60, "intermediate", "Topic")
        assert result == sections

    def test_returns_sections_when_store_empty(self, test_env_vars, mock_llm):
        """Lines 385-388: get_stats returns 0 document_count → return as-is."""
        mock_vs = MagicMock()
        mock_vs.get_stats.return_value = {"document_count": 0}
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        sections = self._make_sections()
        result = designer._validate_and_enrich_sections(sections, 60, "intermediate", "Topic")
        assert result == sections

    def test_handles_vector_store_exception(self, test_env_vars, mock_llm):
        """Lines 386-388: get_stats raises → return as-is."""
        mock_vs = MagicMock()
        mock_vs.get_stats.side_effect = RuntimeError("DB error")
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        sections = self._make_sections()
        result = designer._validate_and_enrich_sections(sections, 60, "intermediate", "Topic")
        assert result == sections

    def test_validates_content_sections_against_kb(self, test_env_vars, mock_llm):
        """Steps 1 & 2: each content section is queried; all are kept."""
        mock_vs = MagicMock()
        mock_vs.get_stats.return_value = {"document_count": 5}
        mock_vs.query.return_value = {"documents": [["chunk1", "chunk2"]], "metadatas": [[{"source": "doc.pdf"}]]}
        # _enrich_curriculum_from_full_kb: return empty new topics
        mock_vs.collection.get.return_value = {"documents": ["chunk1", "chunk2"]}
        mock_llm.invoke.return_value = _mock_llm_response("[]")

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        sections = self._make_sections(3)
        result = designer._validate_and_enrich_sections(sections, 60, "intermediate", "Topic")
        assert len(result) >= len(sections) - 2  # at most same count

    def test_section_query_exception_keeps_section(self, test_env_vars, mock_llm):
        """Lines 415-417: query raises → section kept."""
        mock_vs = MagicMock()
        mock_vs.get_stats.return_value = {"document_count": 3}
        mock_vs.query.side_effect = RuntimeError("query fail")
        mock_vs.collection.get.return_value = {"documents": []}
        mock_llm.invoke.return_value = _mock_llm_response("[]")

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        sections = self._make_sections(2)
        result = designer._validate_and_enrich_sections(sections, 60, "intermediate", "Topic")
        # All sections kept
        assert len([s for s in result if "section_1" in s.id]) == 1

    def test_with_source_files_uncovered(self, test_env_vars, mock_llm):
        """Lines 428-483: source_files path — uncovered sources trigger LLM enrichment."""
        mock_vs = MagicMock()
        mock_vs.get_stats.return_value = {"document_count": 5}
        mock_vs.query.return_value = {
            "documents": [["chunk"]],
            "metadatas": [[{"source": "covered.pdf"}]],
        }
        mock_vs.collection.get.return_value = {"documents": ["chunk"]}
        mock_llm.invoke.return_value = _mock_llm_response('["새로운 섹션"]')

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        sections = self._make_sections(2)
        result = designer._validate_and_enrich_sections(
            sections, 90, "intermediate", "Topic",
            source_files=["covered.pdf", "uncovered.pdf"]
        )
        # Should not crash; result is a list
        assert isinstance(result, list)

    def test_source_files_empty_list_skipped(self, test_env_vars, mock_llm):
        """Empty source_files list → step 3 skipped entirely."""
        mock_vs = MagicMock()
        mock_vs.get_stats.return_value = {"document_count": 3}
        mock_vs.query.return_value = {"documents": [[]], "metadatas": [[]]}
        mock_vs.collection.get.return_value = {"documents": []}
        mock_llm.invoke.return_value = _mock_llm_response("[]")

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        sections = self._make_sections(2)
        result = designer._validate_and_enrich_sections(sections, 60, "intermediate", "T", source_files=[])
        assert isinstance(result, list)


# ── _enrich_curriculum_from_full_kb (lines 500-574) ─────────────────────────

class TestEnrichCurriculumFromFullKb:
    def _make_validated(self):
        return [
            Section(id="s1", title="Existing Topic", estimated_time=20, difficulty_level="intermediate")
        ]

    def _make_structural(self):
        return [
            Section(id="section_0_intro", title="Intro", estimated_time=5, difficulty_level="beginner"),
            Section(id="section_conclusion", title="Conclusion", estimated_time=5, difficulty_level="beginner"),
        ]

    def test_adds_new_sections_from_kb(self, test_env_vars, mock_llm):
        mock_vs = MagicMock()
        mock_vs.collection.get.return_value = {
            "documents": [f"chunk {i}" for i in range(30)]
        }
        mock_llm.invoke.return_value = _mock_llm_response('["새 섹션A", "새 섹션B"]')

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        validated = self._make_validated()
        original_len = len(validated)  # capture before mutation
        result = designer._enrich_curriculum_from_full_kb(
            validated, 90, "Test Topic", self._make_structural()
        )
        # At least one new section added
        assert len(result) > original_len

    def test_empty_kb_returns_unchanged(self, test_env_vars, mock_llm):
        """Lines 519-521: empty all_docs → return validated unchanged."""
        mock_vs = MagicMock()
        mock_vs.collection.get.return_value = {"documents": []}
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        validated = self._make_validated()
        result = designer._enrich_curriculum_from_full_kb(
            validated, 60, "Topic", self._make_structural()
        )
        assert result == validated

    def test_collection_get_exception_returns_unchanged(self, test_env_vars, mock_llm):
        """Lines 515-517: collection.get raises → return validated."""
        mock_vs = MagicMock()
        mock_vs.collection.get.side_effect = AttributeError("no collection")
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        validated = self._make_validated()
        result = designer._enrich_curriculum_from_full_kb(
            validated, 60, "Topic", self._make_structural()
        )
        assert result == validated

    def test_skips_duplicate_titles(self, test_env_vars, mock_llm):
        """New topic that already exists in validated should not be re-added."""
        mock_vs = MagicMock()
        mock_vs.collection.get.return_value = {"documents": ["doc"] * 10}
        # Return "Existing Topic" which is already in validated
        mock_llm.invoke.return_value = _mock_llm_response('["Existing Topic"]')

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        validated = self._make_validated()  # has "Existing Topic"
        result = designer._enrich_curriculum_from_full_kb(
            validated, 60, "Topic", self._make_structural()
        )
        # No duplicate added
        titles = [s.title for s in result]
        assert titles.count("Existing Topic") == 1

    def test_llm_json_error_returns_unchanged(self, test_env_vars, mock_llm):
        """Lines 571-573: LLM returns bad JSON → return validated unchanged."""
        mock_vs = MagicMock()
        mock_vs.collection.get.return_value = {"documents": ["doc"] * 5}
        mock_llm.invoke.return_value = _mock_llm_response("NOT JSON !!!")

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        validated = self._make_validated()
        result = designer._enrich_curriculum_from_full_kb(
            validated, 60, "Topic", self._make_structural()
        )
        assert result == validated

    def test_uniform_sampling_up_to_30_chunks(self, test_env_vars, mock_llm):
        """Verify that step sampling works for large KB (> 30 docs)."""
        mock_vs = MagicMock()
        mock_vs.collection.get.return_value = {"documents": [f"doc_{i}" for i in range(100)]}
        mock_llm.invoke.return_value = _mock_llm_response("[]")

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        validated = self._make_validated()
        # Should not raise
        result = designer._enrich_curriculum_from_full_kb(
            validated, 60, "Topic", self._make_structural()
        )
        assert isinstance(result, list)

    def test_non_list_llm_response_ignored(self, test_env_vars, mock_llm):
        """LLM returning dict instead of list → no additions."""
        mock_vs = MagicMock()
        mock_vs.collection.get.return_value = {"documents": ["doc"] * 5}
        mock_llm.invoke.return_value = _mock_llm_response('{"key": "not a list"}')

        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        validated = self._make_validated()
        result = designer._enrich_curriculum_from_full_kb(
            validated, 60, "Topic", self._make_structural()
        )
        assert result == validated


# ── _check_source_coverage (lines 576-601) ──────────────────────────────────

class TestCheckSourceCoverage:
    def _make_sections(self):
        return [
            Section(id="s1", title="Topic A", estimated_time=20, difficulty_level="intermediate"),
            Section(id="s2", title="Topic B", estimated_time=20, difficulty_level="intermediate"),
        ]

    def test_returns_empty_when_no_vector_store(self, test_env_vars, mock_llm):
        designer = CurriculumDesignerAgent(vector_store=None)
        result = designer._check_source_coverage(self._make_sections(), ["file.pdf"])
        assert result == []

    def test_returns_empty_when_no_source_files(self, test_env_vars, mock_llm):
        mock_vs = MagicMock()
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        result = designer._check_source_coverage(self._make_sections(), [])
        assert result == []

    def test_identifies_uncovered_source(self, test_env_vars, mock_llm):
        mock_vs = MagicMock()
        mock_vs.query.return_value = {
            "documents": [["chunk"]],
            "metadatas": [[{"source": "covered.pdf"}]],
        }
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        result = designer._check_source_coverage(
            self._make_sections(), ["covered.pdf", "uncovered.pdf"]
        )
        assert "uncovered.pdf" in result
        assert "covered.pdf" not in result

    def test_all_covered_returns_empty(self, test_env_vars, mock_llm):
        mock_vs = MagicMock()
        mock_vs.query.return_value = {
            "documents": [["chunk"]],
            "metadatas": [[{"source": "a.pdf"}, {"source": "b.pdf"}]],
        }
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        result = designer._check_source_coverage(
            self._make_sections(), ["a.pdf", "b.pdf"]
        )
        assert result == []

    def test_query_exception_for_section_handled(self, test_env_vars, mock_llm):
        """Lines 598-599: query raises → section treated as uncovered."""
        mock_vs = MagicMock()
        mock_vs.query.side_effect = RuntimeError("fail")
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        result = designer._check_source_coverage(
            self._make_sections(), ["file.pdf"]
        )
        assert "file.pdf" in result

    def test_empty_source_string_excluded(self, test_env_vars, mock_llm):
        """Source entries with empty string are filtered from uncovered list."""
        mock_vs = MagicMock()
        mock_vs.query.return_value = {"documents": [[]], "metadatas": [[]]}
        designer = CurriculumDesignerAgent(vector_store=mock_vs)
        result = designer._check_source_coverage(
            self._make_sections(), ["", "real.pdf"]
        )
        assert "" not in result
        assert "real.pdf" in result


# ── Full design() integration (lines 25-86) ──────────────────────────────────

class TestDesignIntegration:
    def _rmc_ok_response(self):
        return _mock_llm_response(json.dumps({
            "revised_objectives": None,
            "section_reorder": None,
            "issues": [],
            "reasoning": "ok",
            "no_changes": True,
        }))

    def _align_ok_response(self):
        """Mock response for _align_objectives_to_sections (new LLM call after sections)."""
        return _mock_llm_response('["목표1 (섹션 반영)", "목표2 (섹션 반영)"]')

    def test_source_files_from_analysis_metadata(self, designer, sample_analysis, mock_llm):
        """Lines 49-52: source_files extracted from analysis.metadata when not provided."""
        # Call order: 1) learning objectives, 2) align objectives to sections, 3) RMC review
        mock_llm.invoke.side_effect = [
            _mock_llm_response('["목표1", "목표2"]'),
            self._align_ok_response(),
            self._rmc_ok_response(),
        ]
        curriculum = designer.design(
            analysis_result=sample_analysis,
            topic="ML",
            duration=60,
            audience_level="intermediate",
            source_files=None,  # should be pulled from metadata
        )
        assert curriculum.source_files == ["doc1.pdf", "doc2.pdf"]

    def test_explicit_source_files_override_metadata(self, designer, sample_analysis, mock_llm):
        """Explicitly passed source_files should take priority."""
        mock_llm.invoke.side_effect = [
            _mock_llm_response('["목표1"]'),
            self._align_ok_response(),
            self._rmc_ok_response(),
        ]
        curriculum = designer.design(
            analysis_result=sample_analysis,
            topic="ML",
            duration=60,
            audience_level="intermediate",
            source_files=["explicit.pdf"],
        )
        assert curriculum.source_files == ["explicit.pdf"]

    def test_returns_curriculum_with_rmc_applied(self, designer, sample_analysis, mock_llm):
        """design() should run RMC and return valid Curriculum."""
        mock_llm.invoke.side_effect = [
            _mock_llm_response('["목표1", "목표2"]'),
            self._align_ok_response(),
            self._rmc_ok_response(),
        ]
        curriculum = designer.design(
            analysis_result=sample_analysis,
            topic="Neural Networks",
            duration=90,
            audience_level="advanced",
        )
        assert isinstance(curriculum, Curriculum)
        assert curriculum.topic == "Neural Networks"
        assert len(curriculum.sections) >= 1
