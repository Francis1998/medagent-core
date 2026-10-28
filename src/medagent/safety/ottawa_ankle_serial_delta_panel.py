"""OttawaAnkleSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Ottawa Ankle serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `OttawaAnkleRuleScorer` / `OttawaKneeRuleScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import OttawaAnkleSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OttawaAnkleSerialDeltaFactors:
    """Simplified OttawaAnkleSerialDeltaPanel factors."""

    prior_ottawa_positive: int = 0
    malleolar_pain_new: int = 0
    navicular_pain_new: int = 0
    base_fifth_pain_new: int = 0
    inability_bear_weight_new: int = 0
    swelling_worsened: int = 0


class OttawaAnkleSerialDeltaPanel:
    """Compute advisory OttawaAnkleSerialDeltaRisk findings."""

    def check(self, factors: OttawaAnkleSerialDeltaFactors) -> list[OttawaAnkleSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_ottawa_positive": factors.prior_ottawa_positive,
            "malleolar_pain_new": factors.malleolar_pain_new,
            "navicular_pain_new": factors.navicular_pain_new,
            "base_fifth_pain_new": factors.base_fifth_pain_new,
            "inability_bear_weight_new": factors.inability_bear_weight_new,
            "swelling_worsened": factors.swelling_worsened,
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
            "RESEARCH USE ONLY: OttawaAnkleSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = OttawaAnkleSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ottawa_ankle_serial_delta_panel_scored", score=score, band=band)
        return [finding]
