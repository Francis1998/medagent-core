"""ApgarScoreScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AAP Apgar newborn score gap for
offline medical-ward agent pipelines.
Distinct from `BishopScoreScorer` / `FourScoreScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ApgarScoreRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ApgarScoreFactors:
    """Simplified ApgarScoreScorer factors."""

    appearance_ok: int = 0
    pulse_ok: int = 0
    grimace_ok: int = 0
    activity_ok: int = 0
    respiration_ok: int = 0


class ApgarScoreScorer:
    """Compute advisory ApgarScoreRisk findings."""

    def check(self, factors: ApgarScoreFactors) -> list[ApgarScoreRisk]:
        """Return one advisory finding."""

        binaries = {
            "appearance_ok": factors.appearance_ok,
            "pulse_ok": factors.pulse_ok,
            "grimace_ok": factors.grimace_ok,
            "activity_ok": factors.activity_ok,
            "respiration_ok": factors.respiration_ok,
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
            "RESEARCH USE ONLY: ApgarScoreScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ApgarScoreRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("apgar_score_scorer_scored", score=score, band=band)
        return [finding]
