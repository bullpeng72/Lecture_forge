"""
Quality Evaluator Agent - Evaluates lecture quality.
"""

from lecture_forge.agents.base import BaseAgent
from lecture_forge.models.evaluation import EvaluationResult
from lecture_forge.models.lecture import Lecture
from lecture_forge.utils import logger


class QualityEvaluatorAgent(BaseAgent):
    """Agent for evaluating lecture quality."""

    def __init__(self, with_code: bool = True):
        super().__init__()
        self.with_code = with_code
        logger.info("Initializing Quality Evaluator Agent")

    def evaluate(self, lecture: Lecture, threshold: int = 80) -> EvaluationResult:
        """
        Evaluate lecture quality.

        Args:
            lecture: Lecture to evaluate
            threshold: Quality threshold (default: 80)

        Returns:
            Evaluation result
        """
        logger.info(f"Evaluating lecture: {lecture.title}")

        # Use the actual quality evaluator
        from lecture_forge.quality.evaluator import QualityEvaluator

        evaluator = QualityEvaluator(with_code=self.with_code)
        result = evaluator.evaluate(lecture, threshold)

        logger.info(
            f"Evaluation complete: {result.overall_score:.1f}/100 "
            f"({result.get_quality_level()}), {len(result.issues)} issues"
        )

        return result
