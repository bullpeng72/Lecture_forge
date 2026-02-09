"""
Evaluation data models.
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class Issue(BaseModel):
    """Quality issue found during evaluation."""

    dimension: str  # content_completeness, logical_flow, etc.
    severity: str  # high, medium, low
    location: str  # section ID or "global"
    description: str
    suggestion: str


class EvaluationResult(BaseModel):
    """Result of quality evaluation."""

    overall_score: float  # 0-100
    passed: bool  # >= threshold
    dimension_scores: Dict[str, float] = Field(
        default_factory=dict
    )  # dimension_name -> score
    issues: List[Issue] = Field(default_factory=list)
    revision_strategy: str = "none"  # "none", "auto", "consult", "major"
    iteration: int = 0

    def is_auto_fixable(self) -> bool:
        """Check if issues can be auto-fixed."""
        if self.overall_score < 60:
            return False  # Too many issues

        high_severity_count = sum(1 for issue in self.issues if issue.severity == "high")
        if high_severity_count > 3:
            return False

        return True

    def get_quality_level(self) -> str:
        """Get quality level description."""
        if self.overall_score >= 90:
            return "Excellent"
        elif self.overall_score >= 80:
            return "Good"
        elif self.overall_score >= 70:
            return "Fair"
        elif self.overall_score >= 60:
            return "Poor"
        else:
            return "Needs Major Revision"
