"""SofaSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / SOFA serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `SofaOrganFailureScorer` / `News2SerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, SofaSerialDeltaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SofaSerialDeltaFactors:
    """Simplified SofaSerialDeltaPanel factors."""

    prior_sofa_elevated: int = 0
    current_sofa_rise: int = 0
    resp_worsening: int = 0
    coag_worsening: int = 0
    liver_worsening: int = 0
    cv_worsening: int = 0


class SofaSerialDeltaPanel:
    """Compute advisory SofaSerialDeltaRisk findings."""

    def check(self, factors: SofaSerialDeltaFactors) -> list[SofaSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_sofa_elevated": factors.prior_sofa_elevated,
            "current_sofa_rise": factors.current_sofa_rise,
            "resp_worsening": factors.resp_worsening,
            "coag_worsening": factors.coag_worsening,
            "liver_worsening": factors.liver_worsening,
            "cv_worsening": factors.cv_worsening,
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
            "RESEARCH USE ONLY: SofaSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = SofaSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("sofa_serial_delta_panel_scored", score=score, band=band)
        return [finding]
