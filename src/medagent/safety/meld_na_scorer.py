"""MeldNaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AASLD / EHR MELD-Na score gap for
offline medical-ward agent pipelines.
Distinct from ``ChildPughLiverSeverityScorer / SofaOrganFailureScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MeldNaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MeldNaFactors:
    """Simplified MeldNaScorer factors."""

    bilirubin_ge_2: int = 0
    inr_ge_1_5: int = 0
    creatinine_ge_1_5: int = 0
    sodium_lt_135: int = 0
    dialysis: int = 0


class MeldNaScorer:
    """Compute advisory MeldNaRisk findings."""

    def check(self, factors: MeldNaFactors) -> list[MeldNaRisk]:
        """Return one advisory finding."""

        binaries = {
            "bilirubin_ge_2": factors.bilirubin_ge_2,
            "inr_ge_1_5": factors.inr_ge_1_5,
            "creatinine_ge_1_5": factors.creatinine_ge_1_5,
            "sodium_lt_135": factors.sodium_lt_135,
            "dialysis": factors.dialysis,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 10:
            band = "low"
            severity = Severity.LOW
        elif score <= 20:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: MeldNaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MeldNaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("meld_na_scorer_scored", score=score, band=band)
        return [finding]
