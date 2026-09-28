"""TimiUaNstemiScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACC / EHR TIMI UA/NSTEMI gap for
offline medical-ward agent pipelines.
Distinct from ``PercPeExclusionScorer / WellsDvtProbabilityScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, TimiUaNstemiRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TimiUaNstemiFactors:
    """Simplified TimiUaNstemiScorer factors."""

    age_ge_65: int = 0
    ge_3_cad_risk_factors: int = 0
    known_cad: int = 0
    aspirin_last_7d: int = 0
    severe_angina: int = 0
    st_deviation: int = 0
    positive_biomarker: int = 0


class TimiUaNstemiScorer:
    """Compute advisory TimiUaNstemiRisk findings."""

    def check(self, factors: TimiUaNstemiFactors) -> list[TimiUaNstemiRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_65": factors.age_ge_65,
            "ge_3_cad_risk_factors": factors.ge_3_cad_risk_factors,
            "known_cad": factors.known_cad,
            "aspirin_last_7d": factors.aspirin_last_7d,
            "severe_angina": factors.severe_angina,
            "st_deviation": factors.st_deviation,
            "positive_biomarker": factors.positive_biomarker,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 2:
            band = "low"
            severity = Severity.LOW
        elif score <= 4:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: TimiUaNstemiScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = TimiUaNstemiRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("timi_ua_nstemi_scorer_scored", score=score, band=band)
        return [finding]
