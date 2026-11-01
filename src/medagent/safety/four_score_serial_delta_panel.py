"""FourScoreSerialDeltaPanel.

Advisory scorer closing the MDCalc / FOUR Score serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `FourScoreScorer` / `GcsSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import FourScoreSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FourScoreSerialDeltaFactors:
    """Simplified FourScoreSerialDeltaPanel factors."""

    prior_four_elevated: int = 0
    eye_response_drop: int = 0
    motor_response_drop: int = 0
    brainstem_worsening: int = 0
    respiration_pattern_worsen: int = 0
    new_intubation: int = 0


class FourScoreSerialDeltaPanel:
    """Compute advisory FourScoreSerialDeltaRisk findings."""

    def check(self, factors: FourScoreSerialDeltaFactors) -> list[FourScoreSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_four_elevated": factors.prior_four_elevated,
            "eye_response_drop": factors.eye_response_drop,
            "motor_response_drop": factors.motor_response_drop,
            "brainstem_worsening": factors.brainstem_worsening,
            "respiration_pattern_worsen": factors.respiration_pattern_worsen,
            "new_intubation": factors.new_intubation,
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
            "RESEARCH USE ONLY: FourScoreSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = FourScoreSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("four_score_serial_delta_panel_scored", score=score, band=band)
        return [finding]
