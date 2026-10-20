"""Curb65SerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / CURB-65 serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `Curb65PneumoniaScorer` / `Crb65PneumoniaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Curb65SerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Curb65SerialDeltaFactors:
    """Simplified Curb65SerialDeltaPanel factors."""

    prior_curb_elevated: int = 0
    current_curb_rise: int = 0
    urea_rise: int = 0
    rr_worsening: int = 0
    bp_drop: int = 0
    confusion_new: int = 0


class Curb65SerialDeltaPanel:
    """Compute advisory Curb65SerialDeltaRisk findings."""

    def check(self, factors: Curb65SerialDeltaFactors) -> list[Curb65SerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_curb_elevated": factors.prior_curb_elevated,
            "current_curb_rise": factors.current_curb_rise,
            "urea_rise": factors.urea_rise,
            "rr_worsening": factors.rr_worsening,
            "bp_drop": factors.bp_drop,
            "confusion_new": factors.confusion_new,
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
            "RESEARCH USE ONLY: Curb65SerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Curb65SerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("curb65_serial_delta_panel_scored", score=score, band=band)
        return [finding]
