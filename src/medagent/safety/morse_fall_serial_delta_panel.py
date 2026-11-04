"""MorseFallSerialDeltaPanel.

Advisory scorer closing the MDCalc / Morse Fall Scale serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `MorseFallScorer` / `BradenPressureScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MorseFallSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MorseFallSerialDeltaFactors:
    """Simplified MorseFallSerialDeltaPanel factors."""

    prior_morse_rise: int = 0
    history_of_falling: int = 0
    secondary_diagnosis_new: int = 0
    ambulatory_aid_change: int = 0
    gait_worsening: int = 0
    mental_status_decline: int = 0


class MorseFallSerialDeltaPanel:
    """Compute advisory MorseFallSerialDeltaRisk findings."""

    def check(self, factors: MorseFallSerialDeltaFactors) -> list[MorseFallSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_morse_rise": factors.prior_morse_rise,
            "history_of_falling": factors.history_of_falling,
            "secondary_diagnosis_new": factors.secondary_diagnosis_new,
            "ambulatory_aid_change": factors.ambulatory_aid_change,
            "gait_worsening": factors.gait_worsening,
            "mental_status_decline": factors.mental_status_decline,
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
            "RESEARCH USE ONLY: MorseFallSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MorseFallSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("morse_fall_serial_delta_panel_scored", score=score, band=band)
        return [finding]
