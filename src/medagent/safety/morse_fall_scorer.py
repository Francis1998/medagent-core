"""MorseFallScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHRQ Morse Fall Scale screen gap for
offline medical-ward agent pipelines.
Distinct from `News2EarlyWarningScorer` / `PewsEarlyWarningScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MorseFallRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MorseFallFactors:
    """Simplified MorseFallScorer factors."""

    history_fall: int = 0
    secondary_diagnosis: int = 0
    ambulatory_aid: int = 0
    iv_therapy: int = 0
    gait_impaired: int = 0
    mental_status: int = 0


class MorseFallScorer:
    """Compute advisory MorseFallRisk findings."""

    def check(self, factors: MorseFallFactors) -> list[MorseFallRisk]:
        """Return one advisory finding."""

        binaries = {
            "history_fall": factors.history_fall,
            "secondary_diagnosis": factors.secondary_diagnosis,
            "ambulatory_aid": factors.ambulatory_aid,
            "iv_therapy": factors.iv_therapy,
            "gait_impaired": factors.gait_impaired,
            "mental_status": factors.mental_status,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= max(2, len(binaries) // 2):
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: MorseFallScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MorseFallRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("morse_fall_scorer_scored", score=score, band=band)
        return [finding]
