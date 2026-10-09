"""BishopScoreScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACOG Bishop score for induction readiness gap for
offline medical-ward agent pipelines.
Distinct from `ApgarScoreScorer` / `FourScoreScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import BishopScoreRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BishopScoreFactors:
    """Simplified BishopScoreScorer factors."""

    dilation_favorable: int = 0
    effacement_favorable: int = 0
    station_favorable: int = 0
    consistency_soft: int = 0
    position_anterior: int = 0


class BishopScoreScorer:
    """Compute advisory BishopScoreRisk findings."""

    def check(self, factors: BishopScoreFactors) -> list[BishopScoreRisk]:
        """Return one advisory finding."""

        binaries = {
            "dilation_favorable": factors.dilation_favorable,
            "effacement_favorable": factors.effacement_favorable,
            "station_favorable": factors.station_favorable,
            "consistency_soft": factors.consistency_soft,
            "position_anterior": factors.position_anterior,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 3:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: BishopScoreScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = BishopScoreRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("bishop_score_scorer_scored", score=score, band=band)
        return [finding]
