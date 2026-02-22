"""
Quality Evaluator - backward-compatible re-export.

QualityEvaluatorAgent was a thin wrapper with no added logic.
Use QualityEvaluator from lecture_forge.quality.evaluator directly.
"""

from lecture_forge.quality.evaluator import QualityEvaluator as QualityEvaluatorAgent  # noqa: F401

__all__ = ["QualityEvaluatorAgent"]
