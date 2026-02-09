"""
Quality evaluator implementation.
"""

from lecture_forge.models.evaluation import EvaluationResult
from lecture_forge.models.lecture import Lecture
from lecture_forge.quality.metrics import QualityMetrics
from lecture_forge.utils import logger


class QualityEvaluator:
    """Evaluates lecture quality."""

    # Metric weights for overall score
    WEIGHTS = {
        "content_completeness": 0.25,
        "logical_flow": 0.20,
        "time_alignment": 0.10,
        "level_appropriateness": 0.20,
        "visual_quality": 0.15,
        "technical_accuracy": 0.10,
    }

    def __init__(self):
        self.metrics = QualityMetrics()
        logger.info("Initializing quality evaluator")

    def evaluate(self, lecture: Lecture, threshold: int = 80) -> EvaluationResult:
        """
        Evaluate lecture quality.

        Args:
            lecture: Lecture to evaluate
            threshold: Pass threshold (default: 80)

        Returns:
            Evaluation result
        """
        logger.info(f"Evaluating lecture: {lecture.title}")

        # Calculate all metrics
        dimension_scores = self.metrics.calculate_all_metrics(lecture)

        # Calculate overall score
        overall_score = sum(dimension_scores[metric] * weight for metric, weight in self.WEIGHTS.items())

        # Determine if passed
        passed = overall_score >= threshold

        # Identify issues
        issues = self._identify_issues(dimension_scores, lecture)

        # Determine revision strategy
        revision_strategy = self._determine_strategy(overall_score, issues)

        result = EvaluationResult(
            overall_score=overall_score,
            passed=passed,
            dimension_scores=dimension_scores,
            issues=issues,
            revision_strategy=revision_strategy,
        )

        logger.info(f"Evaluation complete: {overall_score:.1f}/100 ({result.get_quality_level()})")

        return result

    def _identify_issues(self, dimension_scores: dict, lecture: Lecture) -> list:
        """Identify specific issues based on scores."""

        issues = []

        for dimension, score in dimension_scores.items():
            if score < 60:
                # High severity
                issue = self._create_issue_for_dimension(dimension, score, lecture, severity="high")
                if issue:
                    issues.append(issue)

            elif score < 70:
                # Medium severity
                issue = self._create_issue_for_dimension(dimension, score, lecture, severity="medium")
                if issue:
                    issues.append(issue)

            elif score < 80:
                # Low severity
                issue = self._create_issue_for_dimension(dimension, score, lecture, severity="low")
                if issue:
                    issues.append(issue)

        return issues

    def _create_issue_for_dimension(self, dimension: str, score: float, lecture: Lecture, severity: str) -> dict:
        """Create specific issue for a dimension."""
        from lecture_forge.models.evaluation import Issue

        if dimension == "content_completeness":
            # Analyze what's missing
            total_code = sum(len(s.code_blocks) for s in lecture.sections)
            expected_code = max(1, lecture.duration // 30)

            # CRITICAL: No code examples at all
            if total_code == 0:
                return Issue(
                    dimension=dimension,
                    severity="high",  # Force high severity
                    location="overall",
                    description=f"🚨 CRITICAL: NO code examples found (0/{expected_code})",
                    suggestion=f"URGENT: Add {expected_code} code examples immediately. Each example should be 20-50 lines with Korean comments and show practical usage.",
                )
            elif total_code < expected_code:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description=f"Insufficient code examples ({total_code} found, {expected_code} expected)",
                    suggestion=f"Add {expected_code - total_code} more code examples with detailed explanations",
                )
            elif lecture.total_word_count < lecture.duration * 150:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description=f"Content too short ({lecture.total_word_count} words for {lecture.duration} min)",
                    suggestion="Expand explanations and add more detailed examples",
                )
            else:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description="Content completeness below target",
                    suggestion="Review learning objectives coverage and add missing content",
                )

        elif dimension == "logical_flow":
            # Check for missing intro/conclusion
            has_intro = any("intro" in s.section_id.lower() for s in lecture.sections)
            has_conclusion = any(
                "conclusion" in s.section_id.lower() or "summary" in s.section_id.lower() for s in lecture.sections
            )

            if not has_intro:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="section_0",
                    description="Missing introduction section",
                    suggestion="Add an introduction section covering learning objectives and overview",
                )
            elif not has_conclusion:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location=f"section_{len(lecture.sections)}",
                    description="Missing conclusion section",
                    suggestion="Add a conclusion section with summary and next steps",
                )
            else:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description="Section flow needs improvement",
                    suggestion="Review section ordering and add better transitions",
                )

        elif dimension == "time_alignment":
            if lecture.total_word_count < lecture.duration * 150:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description=f"Content too short for {lecture.duration} minutes",
                    suggestion=f"Add approximately {lecture.duration * 150 - lecture.total_word_count} more words",
                )
            elif lecture.total_word_count > lecture.duration * 250:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description=f"Content too long for {lecture.duration} minutes",
                    suggestion="Consider condensing or splitting into multiple lectures",
                )
            else:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description="Section time balance needs adjustment",
                    suggestion="Redistribute content more evenly across sections",
                )

        elif dimension == "level_appropriateness":
            return Issue(
                dimension=dimension,
                severity=severity,
                location="overall",
                description=f"Content level may not match {lecture.audience_level} audience",
                suggestion="Review technical complexity and adjust explanations accordingly",
            )

        elif dimension == "visual_quality":
            if lecture.total_diagrams < len(lecture.sections) // 2:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description=f"Insufficient diagrams ({lecture.total_diagrams} found)",
                    suggestion=f"Add {len(lecture.sections) // 2 - lecture.total_diagrams} more diagrams to key sections",
                )
            elif lecture.total_images < lecture.duration // 20:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description=f"Insufficient images ({lecture.total_images} found)",
                    suggestion=f"Add {lecture.duration // 20 - lecture.total_images} more relevant images",
                )
            else:
                return Issue(
                    dimension=dimension,
                    severity=severity,
                    location="overall",
                    description="Visual content needs better distribution",
                    suggestion="Ensure each major section has at least one diagram or image",
                )

        elif dimension == "technical_accuracy":
            return Issue(
                dimension=dimension,
                severity=severity,
                location="overall",
                description="Technical accuracy below target",
                suggestion="Review code examples for syntax errors and verify technical claims",
            )

        return None

    def _determine_strategy(self, overall_score: float, issues: list) -> str:
        """Determine revision strategy based on score and issues."""
        if overall_score >= 80:
            return "none"
        elif overall_score >= 70 and len(issues) <= 3:
            return "auto"
        elif overall_score >= 60:
            return "consult"
        else:
            return "major"
