"""CamIcuSerialDeltaPanel.

Advisory scorer closing the MDCalc / CAM-ICU delirium serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `CamIcuDeliriumScorer` / `FourAtSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CamIcuSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CamIcuSerialDeltaFactors:
    """Simplified CamIcuSerialDeltaPanel factors."""

    prior_cam_positive: int = 0
    fluctuation_rise: int = 0
    inattention_worsening: int = 0
    disorganized_thinking: int = 0
    altered_loc: int = 0
    sleep_wake_disruption: int = 0


class CamIcuSerialDeltaPanel:
    """Compute advisory CamIcuSerialDeltaRisk findings."""

    def check(self, factors: CamIcuSerialDeltaFactors) -> list[CamIcuSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_cam_positive": factors.prior_cam_positive,
            "fluctuation_rise": factors.fluctuation_rise,
            "inattention_worsening": factors.inattention_worsening,
            "disorganized_thinking": factors.disorganized_thinking,
            "altered_loc": factors.altered_loc,
            "sleep_wake_disruption": factors.sleep_wake_disruption,
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
            "RESEARCH USE ONLY: CamIcuSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CamIcuSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("cam_icu_serial_delta_panel_scored", score=score, band=band)
        return [finding]
