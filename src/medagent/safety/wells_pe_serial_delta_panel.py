"""WellsPeSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Wells PE serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `WellsPeProbabilityScorer` / `PsiPortPneumoniaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WellsPeSerialDeltaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WellsPeSerialDeltaFactors:
    """Simplified WellsPeSerialDeltaPanel factors."""

    prior_wells_elevated: int = 0
    current_wells_rise: int = 0
    dvt_signs_worsening: int = 0
    hr_worsening: int = 0
    immobilization_new: int = 0
    hemoptysis_new: int = 0


class WellsPeSerialDeltaPanel:
    """Compute advisory WellsPeSerialDeltaRisk findings."""

    def check(self, factors: WellsPeSerialDeltaFactors) -> list[WellsPeSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_wells_elevated": factors.prior_wells_elevated,
            "current_wells_rise": factors.current_wells_rise,
            "dvt_signs_worsening": factors.dvt_signs_worsening,
            "hr_worsening": factors.hr_worsening,
            "immobilization_new": factors.immobilization_new,
            "hemoptysis_new": factors.hemoptysis_new,
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
            "RESEARCH USE ONLY: WellsPeSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WellsPeSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("wells_pe_serial_delta_panel_scored", score=score, band=band)
        return [finding]
