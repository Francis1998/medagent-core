"""NortonSerialDeltaPanel.

Advisory scorer closing the MDCalc / Norton pressure-ulcer serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `BradenSerialDeltaPanel` / `WaterlowSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import NortonSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NortonSerialDeltaFactors:
    """Simplified NortonSerialDeltaPanel factors."""

    physical_condition_worsening: int = 0
    mental_condition_worsening: int = 0
    activity_worsening: int = 0
    mobility_worsening: int = 0
    incontinence_worsening: int = 0
    nutrition_worsening: int = 0


class NortonSerialDeltaPanel:
    """Compute advisory NortonSerialDeltaRisk findings."""

    def check(self, factors: NortonSerialDeltaFactors) -> list[NortonSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "physical_condition_worsening": factors.physical_condition_worsening,
            "mental_condition_worsening": factors.mental_condition_worsening,
            "activity_worsening": factors.activity_worsening,
            "mobility_worsening": factors.mobility_worsening,
            "incontinence_worsening": factors.incontinence_worsening,
            "nutrition_worsening": factors.nutrition_worsening,
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
            "RESEARCH USE ONLY: NortonSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = NortonSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("norton_serial_delta_panel_scored", score=score, band=band)
        return [finding]
