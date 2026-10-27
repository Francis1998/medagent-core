"""NihssSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / NIHSS serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `NihssStrokeScorer` / `GcsNeurologicStatusScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import NihssSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NihssSerialDeltaFactors:
    """Simplified NihssSerialDeltaPanel factors."""

    prior_nihss_elevated: int = 0
    loc_worse: int = 0
    motor_worse: int = 0
    language_worse: int = 0
    gaze_worse: int = 0
    sensory_worse: int = 0


class NihssSerialDeltaPanel:
    """Compute advisory NihssSerialDeltaRisk findings."""

    def check(self, factors: NihssSerialDeltaFactors) -> list[NihssSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_nihss_elevated": factors.prior_nihss_elevated,
            "loc_worse": factors.loc_worse,
            "motor_worse": factors.motor_worse,
            "language_worse": factors.language_worse,
            "gaze_worse": factors.gaze_worse,
            "sensory_worse": factors.sensory_worse,
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
            "RESEARCH USE ONLY: NihssSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = NihssSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("nihss_serial_delta_panel_scored", score=score, band=band)
        return [finding]
