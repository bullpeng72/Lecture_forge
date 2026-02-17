"""
Unit tests for RevisionPlanner.
"""

import pytest

from lecture_forge.models.evaluation import EvaluationResult, Issue
from lecture_forge.models.lecture import Lecture, SectionContent
from lecture_forge.quality.revision_planner import RevisionPlanner


def make_issue(dimension="content_completeness", severity="medium", description="test issue", suggestion="fix it"):
    return Issue(
        dimension=dimension,
        severity=severity,
        location="overall",
        description=description,
        suggestion=suggestion,
    )


def make_evaluation(overall_score=75.0, issues=None, revision_strategy="auto"):
    return EvaluationResult(
        overall_score=overall_score,
        passed=overall_score >= 80,
        dimension_scores={
            "content_completeness": overall_score,
            "logical_flow": overall_score,
            "time_alignment": overall_score,
            "level_appropriateness": overall_score,
            "visual_quality": overall_score,
            "technical_accuracy": overall_score,
        },
        issues=issues or [],
        revision_strategy=revision_strategy,
    )


def make_lecture():
    return Lecture(
        title="Test Lecture",
        topic="Testing",
        duration=60,
        audience_level="intermediate",
        sections=[],
    )


@pytest.fixture
def planner():
    return RevisionPlanner()


class TestCreateRevisionPlan:
    def test_returns_dict_with_required_keys(self, planner):
        evaluation = make_evaluation()
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)

        assert "strategy" in plan
        assert "actions" in plan
        assert "priority" in plan

    def test_strategy_matches_evaluation(self, planner):
        evaluation = make_evaluation(revision_strategy="auto")
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)
        assert plan["strategy"] == "auto"

    def test_no_issues_produces_empty_actions(self, planner):
        evaluation = make_evaluation(issues=[])
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)
        assert plan["actions"] == []

    def test_actions_count_matches_issues_count(self, planner):
        issues = [make_issue("content_completeness"), make_issue("logical_flow"), make_issue("visual_quality")]
        evaluation = make_evaluation(issues=issues)
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)
        assert len(plan["actions"]) == len(issues)

    def test_priority_high_when_score_below_70(self, planner):
        evaluation = make_evaluation(overall_score=65.0)
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)
        assert plan["priority"] == "high"

    def test_priority_medium_when_score_above_70(self, planner):
        evaluation = make_evaluation(overall_score=75.0)
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)
        assert plan["priority"] == "medium"

    def test_priority_medium_at_exactly_70(self, planner):
        evaluation = make_evaluation(overall_score=70.0)
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)
        assert plan["priority"] == "medium"

    def test_action_has_required_fields(self, planner):
        issue = make_issue()
        evaluation = make_evaluation(issues=[issue])
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)

        action = plan["actions"][0]
        assert "issue" in action
        assert "type" in action
        assert "target" in action
        assert "instruction" in action

    def test_action_target_matches_issue_location(self, planner):
        issue = Issue(
            dimension="content_completeness",
            severity="medium",
            location="section_2",
            description="test",
            suggestion="fix",
        )
        evaluation = make_evaluation(issues=[issue])
        lecture = make_lecture()
        plan = planner.create_revision_plan(evaluation, lecture)

        assert plan["actions"][0]["target"] == "section_2"


class TestDetermineActionType:
    def test_visual_quality_diagram_returns_add_diagram(self, planner):
        issue = make_issue("visual_quality", description="Insufficient diagrams")
        action_type = planner._determine_action_type(issue)
        assert action_type == "add_diagram"

    def test_visual_quality_image_returns_add_image(self, planner):
        issue = make_issue("visual_quality", description="Insufficient images")
        action_type = planner._determine_action_type(issue)
        assert action_type == "add_image"

    def test_visual_quality_other_returns_add_visual(self, planner):
        issue = make_issue("visual_quality", description="Visual content needs better distribution")
        action_type = planner._determine_action_type(issue)
        assert action_type == "add_visual"

    def test_content_completeness_code_returns_add_code_example(self, planner):
        issue = make_issue("content_completeness", description="NO code examples found")
        action_type = planner._determine_action_type(issue)
        assert action_type == "add_code_example"

    def test_content_completeness_short_returns_expand_content(self, planner):
        issue = make_issue("content_completeness", description="Content too short for 60 minutes")
        action_type = planner._determine_action_type(issue)
        assert action_type == "expand_content"

    def test_logical_flow_intro_returns_add_introduction(self, planner):
        issue = make_issue("logical_flow", description="Missing introduction section")
        action_type = planner._determine_action_type(issue)
        assert action_type == "add_introduction"

    def test_logical_flow_conclusion_returns_add_conclusion(self, planner):
        issue = make_issue("logical_flow", description="Missing conclusion section")
        action_type = planner._determine_action_type(issue)
        assert action_type == "add_conclusion"

    def test_time_alignment_short_returns_expand_content(self, planner):
        issue = make_issue("time_alignment", description="Content too short for 60 minutes")
        action_type = planner._determine_action_type(issue)
        assert action_type == "expand_content"

    def test_time_alignment_long_returns_condense_content(self, planner):
        issue = make_issue("time_alignment", description="Content too long for 60 minutes")
        action_type = planner._determine_action_type(issue)
        assert action_type == "condense_content"

    def test_technical_accuracy_returns_fact_check_and_fix(self, planner):
        issue = make_issue("technical_accuracy", description="Technical accuracy below target")
        action_type = planner._determine_action_type(issue)
        assert action_type == "fact_check_and_fix"

    def test_unknown_dimension_returns_revise_content(self, planner):
        issue = make_issue("unknown_dimension", description="something")
        action_type = planner._determine_action_type(issue)
        assert action_type == "revise_content"
