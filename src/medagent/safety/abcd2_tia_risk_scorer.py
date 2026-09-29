"""Abcd2TiaRiskScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA / EHR ABCD2 TIA risk gap for
offline medical-ward agent pipelines.
Distinct from ``NihssStrokeScorer / Cha2ds2VascStrokeRiskScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Abcd2TiaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Abcd2TiaFactors:
    """Simplified Abcd2TiaRiskScorer factors."""

    age_ge_60: int = 0
    bp_ge_140_90: int = 0
    unilateral_weakness: int = 0
    speech_impairment_no_weakness: int = 0
    duration_ge_60_min: int = 0
    diabetes: int = 0


class Abcd2TiaRiskScorer:
    """Compute advisory Abcd2TiaRisk findings."""

    def check(self, factors: Abcd2TiaFactors) -> list[Abcd2TiaRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_60": factors.age_ge_60,
            "bp_ge_140_90": factors.bp_ge_140_90,
            "unilateral_weakness": factors.unilateral_weakness,
            "speech_impairment_no_weakness": factors.speech_impairment_no_weakness,
            "duration_ge_60_min": factors.duration_ge_60_min,
            "diabetes": factors.diabetes,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low_risk"
            severity = Severity.LOW
        elif score <= 3:
            band = "moderate_risk"
            severity = Severity.MODERATE
        else:
            band = "high_risk"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: Abcd2TiaRiskScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Abcd2TiaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("abcd2_tia_risk_scorer_scored", score=score, band=band)
        return [finding]
