"""GenevaPeSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Geneva PE serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `RevisedGenevaPeScorer` / `WellsPeSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import GenevaPeSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GenevaPeSerialDeltaFactors:
    """Simplified GenevaPeSerialDeltaPanel factors."""

    prior_geneva_elevated: int = 0
    current_geneva_rise: int = 0
    hr_worsening: int = 0
    hemoptysis_new: int = 0
    unilateral_pain_worsening: int = 0
    spo2_worsening: int = 0


class GenevaPeSerialDeltaPanel:
    """Compute advisory GenevaPeSerialDeltaRisk findings."""

    def check(self, factors: GenevaPeSerialDeltaFactors) -> list[GenevaPeSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_geneva_elevated": factors.prior_geneva_elevated,
            "current_geneva_rise": factors.current_geneva_rise,
            "hr_worsening": factors.hr_worsening,
            "hemoptysis_new": factors.hemoptysis_new,
            "unilateral_pain_worsening": factors.unilateral_pain_worsening,
            "spo2_worsening": factors.spo2_worsening,
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
            "RESEARCH USE ONLY: GenevaPeSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = GenevaPeSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("geneva_pe_serial_delta_panel_scored", score=score, band=band)
        return [finding]
