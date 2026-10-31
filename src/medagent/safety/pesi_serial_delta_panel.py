"""PesiSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / PESI PE severity serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `PesiPeSeverityScorer` / `WellsPeSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PesiSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PesiSerialDeltaFactors:
    """Simplified PesiSerialDeltaPanel factors."""

    prior_pesi_elevated: int = 0
    hr_rise: int = 0
    sbp_drop: int = 0
    o2_sat_drop: int = 0
    mental_status_worsen: int = 0
    rr_rise: int = 0


class PesiSerialDeltaPanel:
    """Compute advisory PesiSerialDeltaRisk findings."""

    def check(self, factors: PesiSerialDeltaFactors) -> list[PesiSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_pesi_elevated": factors.prior_pesi_elevated,
            "hr_rise": factors.hr_rise,
            "sbp_drop": factors.sbp_drop,
            "o2_sat_drop": factors.o2_sat_drop,
            "mental_status_worsen": factors.mental_status_worsen,
            "rr_rise": factors.rr_rise,
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
            "RESEARCH USE ONLY: PesiSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PesiSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("pesi_serial_delta_panel_scored", score=score, band=band)
        return [finding]
