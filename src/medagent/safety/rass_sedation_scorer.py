"""RassSedationScorer (research-only clinical score).

Advisory scorer closing the MDCalc / SCCM Richmond Agitation-Sedation Scale (RASS) screen gap for
offline medical-ward agent pipelines.
Distinct from `CamIcuDeliriumScorer` / `CiwaArWithdrawalScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RassSedationRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RassSedationFactors:
    """Simplified RassSedationScorer factors."""

    restless_agitated: int = 0
    combative: int = 0
    drowsy: int = 0
    light_sedation: int = 0
    moderate_sedation: int = 0
    deep_sedation: int = 0


class RassSedationScorer:
    """Compute advisory RassSedationRisk findings."""

    def check(self, factors: RassSedationFactors) -> list[RassSedationRisk]:
        """Return one advisory finding."""

        binaries = {
            "restless_agitated": factors.restless_agitated,
            "combative": factors.combative,
            "drowsy": factors.drowsy,
            "light_sedation": factors.light_sedation,
            "moderate_sedation": factors.moderate_sedation,
            "deep_sedation": factors.deep_sedation,
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
            "RESEARCH USE ONLY: RassSedationScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RassSedationRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("rass_sedation_scorer_scored", score=score, band=band)
        return [finding]
