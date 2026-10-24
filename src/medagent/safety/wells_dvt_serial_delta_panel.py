"""WellsDvtSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Wells DVT serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `WellsDvtProbabilityScorer` / `WellsPeSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WellsDvtSerialDeltaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WellsDvtSerialDeltaFactors:
    """Simplified WellsDvtSerialDeltaPanel factors."""

    prior_wells_dvt_elevated: int = 0
    current_wells_dvt_rise: int = 0
    calf_swelling_worsening: int = 0
    tenderness_worsening: int = 0
    immobility_worsening: int = 0
    alt_diagnosis_less_likely: int = 0


class WellsDvtSerialDeltaPanel:
    """Compute advisory WellsDvtSerialDeltaRisk findings."""

    def check(self, factors: WellsDvtSerialDeltaFactors) -> list[WellsDvtSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_wells_dvt_elevated": factors.prior_wells_dvt_elevated,
            "current_wells_dvt_rise": factors.current_wells_dvt_rise,
            "calf_swelling_worsening": factors.calf_swelling_worsening,
            "tenderness_worsening": factors.tenderness_worsening,
            "immobility_worsening": factors.immobility_worsening,
            "alt_diagnosis_less_likely": factors.alt_diagnosis_less_likely,
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
            "RESEARCH USE ONLY: WellsDvtSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WellsDvtSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("wells_dvt_serial_delta_panel_scored", score=score, band=band)
        return [finding]
