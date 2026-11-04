"""BradenSerialDeltaPanel.

Advisory scorer closing the MDCalc / Braden pressure-injury serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `BradenPressureScorer` / `MorseFallScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import BradenSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BradenSerialDeltaFactors:
    """Simplified BradenSerialDeltaPanel factors."""

    prior_braden_drop: int = 0
    mobility_worsening: int = 0
    moisture_rise: int = 0
    nutrition_decline: int = 0
    friction_shear_rise: int = 0
    activity_decline: int = 0


class BradenSerialDeltaPanel:
    """Compute advisory BradenSerialDeltaRisk findings."""

    def check(self, factors: BradenSerialDeltaFactors) -> list[BradenSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_braden_drop": factors.prior_braden_drop,
            "mobility_worsening": factors.mobility_worsening,
            "moisture_rise": factors.moisture_rise,
            "nutrition_decline": factors.nutrition_decline,
            "friction_shear_rise": factors.friction_shear_rise,
            "activity_decline": factors.activity_decline,
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
            "RESEARCH USE ONLY: BradenSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = BradenSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("braden_serial_delta_panel_scored", score=score, band=band)
        return [finding]
