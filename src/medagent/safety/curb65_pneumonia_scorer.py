"""Curb65PneumoniaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / BTS / EHR CURB-65 calculator gap for offline agent pipelines.
Distinct from ``ChildPughLiverSeverityScorer / VitalsTriageChecker``. Prefer GPT-5.5 / Claude
Sonnet 4.6 /
Gemini 3.x / Kimi K2 for narrative summaries. Never modifies medications and
never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Curb65PneumoniaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Curb65Factors:
    """Input factors for Curb65PneumoniaScorer."""

    confusion: bool = False
    urea_over_7: bool = False
    resp_rate_30_plus: bool = False
    low_blood_pressure: bool = False
    age_65_plus: bool = False


class Curb65PneumoniaScorer:
    """Compute advisory Curb65PneumoniaRisk findings."""

    def check(self, factors: Curb65Factors) -> list[Curb65PneumoniaRisk]:
        """Return one advisory finding."""

        mapping = {
            "confusion": factors.confusion,
            "urea_over_7": factors.urea_over_7,
            "resp_rate_30_plus": factors.resp_rate_30_plus,
            "low_blood_pressure": factors.low_blood_pressure,
            "age_65_plus": factors.age_65_plus,
        }
        positive = [k for k, v in mapping.items() if v]
        score = len(positive)

        if score >= 3:
            band = "severe"
            severity = Severity.HIGH
        elif score >= 2:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "mild"
            severity = Severity.LOW

        rationale = (
            "RESEARCH USE ONLY: Curb65PneumoniaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Curb65PneumoniaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("curb65_pneumonia_scorer_scored", score=score, band=band)
        return [finding]
