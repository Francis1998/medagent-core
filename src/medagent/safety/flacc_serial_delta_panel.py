"""FlaccSerialDeltaPanel.

Advisory scorer closing the MDCalc / FLACC pediatric pain serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `RassSerialDeltaPanel` / `FourAtSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import FlaccSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FlaccSerialDeltaFactors:
    """Simplified FlaccSerialDeltaPanel factors."""

    face_worsening: int = 0
    legs_worsening: int = 0
    activity_worsening: int = 0
    cry_worsening: int = 0
    consolability_worsening: int = 0
    caregiver_concern: int = 0


class FlaccSerialDeltaPanel:
    """Compute advisory FlaccSerialDeltaRisk findings."""

    def check(self, factors: FlaccSerialDeltaFactors) -> list[FlaccSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "face_worsening": factors.face_worsening,
            "legs_worsening": factors.legs_worsening,
            "activity_worsening": factors.activity_worsening,
            "cry_worsening": factors.cry_worsening,
            "consolability_worsening": factors.consolability_worsening,
            "caregiver_concern": factors.caregiver_concern,
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
            "RESEARCH USE ONLY: FlaccSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = FlaccSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("flacc_serial_delta_panel_scored", score=score, band=band)
        return [finding]
