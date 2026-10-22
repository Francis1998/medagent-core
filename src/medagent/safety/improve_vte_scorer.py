"""ImproveVteScorer (research-only clinical score).

Advisory scorer closing the MDCalc / IMPROVE VTE risk screen gap for
offline medical-ward agent pipelines.
Distinct from `PaduaVteRiskScorer` / `WellsPeProbabilityScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ImproveVteRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ImproveVteFactors:
    """Simplified ImproveVteScorer factors."""

    prior_vte: int = 0
    known_thrombophilia: int = 0
    active_cancer: int = 0
    icu_stay: int = 0
    lower_limb_paralysis: int = 0
    immobilization_7d: int = 0


class ImproveVteScorer:
    """Compute advisory ImproveVteRisk findings."""

    def check(self, factors: ImproveVteFactors) -> list[ImproveVteRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_vte": factors.prior_vte,
            "known_thrombophilia": factors.known_thrombophilia,
            "active_cancer": factors.active_cancer,
            "icu_stay": factors.icu_stay,
            "lower_limb_paralysis": factors.lower_limb_paralysis,
            "immobilization_7d": factors.immobilization_7d,
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
            "RESEARCH USE ONLY: ImproveVteScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ImproveVteRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("improve_vte_scorer_scored", score=score, band=band)
        return [finding]
