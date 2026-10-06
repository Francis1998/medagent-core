"""IchScoreScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA ICH score gap for
offline medical-ward agent pipelines.
Distinct from ``WfnsSahScorer / HuntHessSahScorer / NihssStrokeScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import IchScoreRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IchScoreFactors:
    """Simplified IchScoreScorer factors."""

    gcs_le_4: int = 0
    ich_volume_ge_30: int = 0
    ivh_present: int = 0
    infratentorial: int = 0
    age_ge_80: int = 0


class IchScoreScorer:
    """Compute advisory IchScoreRisk findings."""

    def check(self, factors: IchScoreFactors) -> list[IchScoreRisk]:
        """Return one advisory finding."""

        binaries = {
            "gcs_le_4": factors.gcs_le_4,
            "ich_volume_ge_30": factors.ich_volume_ge_30,
            "ivh_present": factors.ivh_present,
            "infratentorial": factors.infratentorial,
            "age_ge_80": factors.age_ge_80,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 2:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: IchScoreScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = IchScoreRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ich_score_scorer_scored", score=score, band=band)
        return [finding]
