"""HasBledSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / HAS-BLED serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `HasBledBleedRiskScorer` / `Cha2ds2VascSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import HasBledSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HasBledSerialDeltaFactors:
    """Simplified HasBledSerialDeltaPanel factors."""

    prior_has_bled_elevated: int = 0
    hypertension_uncontrolled_new: int = 0
    renal_liver_worsened: int = 0
    stroke_history_new: int = 0
    bleeding_history_new: int = 0
    labile_inr_new: int = 0


class HasBledSerialDeltaPanel:
    """Compute advisory HasBledSerialDeltaRisk findings."""

    def check(self, factors: HasBledSerialDeltaFactors) -> list[HasBledSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_has_bled_elevated": factors.prior_has_bled_elevated,
            "hypertension_uncontrolled_new": factors.hypertension_uncontrolled_new,
            "renal_liver_worsened": factors.renal_liver_worsened,
            "stroke_history_new": factors.stroke_history_new,
            "bleeding_history_new": factors.bleeding_history_new,
            "labile_inr_new": factors.labile_inr_new,
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
            "RESEARCH USE ONLY: HasBledSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = HasBledSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("has_bled_serial_delta_panel_scored", score=score, band=band)
        return [finding]
