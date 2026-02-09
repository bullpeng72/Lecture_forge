"""
Revision planner for lecture improvements.
"""

from typing import Dict

from lecture_forge.models.evaluation import EvaluationResult, Issue
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger


class RevisionPlanner:
    """Plans revisions based on evaluation results."""

    def __init__(self):
        logger.info("Initializing revision planner")

    def create_revision_plan(self, evaluation: EvaluationResult, lecture: Lecture) -> Dict:
        """
        Create a revision plan based on evaluation.

        Args:
            evaluation: Evaluation result
            lecture: Current lecture

        Returns:
            Revision plan with actions
        """
        logger.info(f"Creating revision plan for {len(evaluation.issues)} issues")

        plan = {
            "strategy": evaluation.revision_strategy,
            "actions": [],
            "priority": "high" if evaluation.overall_score < 70 else "medium",
        }

        for issue in evaluation.issues:
            action = self._create_action(issue, lecture)
            plan["actions"].append(action)

        return plan

    def _create_action(self, issue: Issue, lecture: Lecture) -> Dict:
        """Create a specific action for an issue."""
        action = {
            "issue": issue,
            "type": self._determine_action_type(issue),
            "target": issue.location,
            "instruction": issue.suggestion,
        }

        return action

    def _determine_action_type(self, issue: Issue) -> str:
        """Determine what type of action is needed."""
        # Dimension-based action determination
        if issue.dimension == "visual_quality":
            if "diagram" in issue.description.lower():
                return "add_diagram"
            elif "image" in issue.description.lower():
                return "add_image"
            else:
                return "add_visual"

        elif issue.dimension == "content_completeness":
            if "code" in issue.description.lower():
                return "add_code_example"
            elif "objective" in issue.description.lower():
                return "add_section"
            elif "short" in issue.description.lower():
                return "expand_content"
            else:
                return "enhance_content"

        elif issue.dimension == "logical_flow":
            if "intro" in issue.description.lower():
                return "add_introduction"
            elif "conclusion" in issue.description.lower():
                return "add_conclusion"
            elif "transition" in issue.description.lower():
                return "improve_transitions"
            else:
                return "reorder_sections"

        elif issue.dimension == "time_alignment":
            if "short" in issue.description.lower():
                return "expand_content"
            elif "long" in issue.description.lower():
                return "condense_content"
            else:
                return "rebalance_sections"

        elif issue.dimension == "level_appropriateness":
            if "complex" in issue.description.lower():
                return "simplify_content"
            elif "basic" in issue.description.lower():
                return "add_advanced_content"
            else:
                return "adjust_level"

        elif issue.dimension == "technical_accuracy":
            return "fact_check_and_fix"

        else:
            return "revise_content"
