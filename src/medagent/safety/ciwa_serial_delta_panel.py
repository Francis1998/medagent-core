"""CiwaSerialDeltaPanel.

Advisory scorer closing the MDCalc / CIWA-Ar withdrawal serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `CiwaArWithdrawalScorer` / `RassSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CiwaSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CiwaSerialDeltaFactors:
    """Simplified CiwaSerialDeltaPanel factors."""

    prior_ciwa_rise: int = 0
    tremor_worsening: int = 0
    anxiety_rise: int = 0
    agitation_rise: int = 0
    orientation_decline: int = 0
    paroxysmal_sweats_rise: int = 0


class CiwaSerialDeltaPanel:
    """Compute advisory CiwaSerialDeltaRisk findings."""

    def check(self, factors: CiwaSerialDeltaFactors) -> list[CiwaSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_ciwa_rise": factors.prior_ciwa_rise,
            "tremor_worsening": factors.tremor_worsening,
            "anxiety_rise": factors.anxiety_rise,
            "agitation_rise": factors.agitation_rise,
            "orientation_decline": factors.orientation_decline,
            "paroxysmal_sweats_rise": factors.paroxysmal_sweats_rise,
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
            "RESEARCH USE ONLY: CiwaSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CiwaSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ciwa_serial_delta_panel_scored", score=score, band=band)
        return [finding]
