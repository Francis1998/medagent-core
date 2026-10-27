"""GcsSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / GCS serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `GcsNeurologicStatusScorer` / `NihssSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import GcsSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GcsSerialDeltaFactors:
    """Simplified GcsSerialDeltaPanel factors."""

    prior_gcs_depressed: int = 0
    eye_down: int = 0
    verbal_down: int = 0
    motor_down: int = 0
    pupil_asymmetry_new: int = 0
    sedation_confound_new: int = 0


class GcsSerialDeltaPanel:
    """Compute advisory GcsSerialDeltaRisk findings."""

    def check(self, factors: GcsSerialDeltaFactors) -> list[GcsSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_gcs_depressed": factors.prior_gcs_depressed,
            "eye_down": factors.eye_down,
            "verbal_down": factors.verbal_down,
            "motor_down": factors.motor_down,
            "pupil_asymmetry_new": factors.pupil_asymmetry_new,
            "sedation_confound_new": factors.sedation_confound_new,
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
            "RESEARCH USE ONLY: GcsSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = GcsSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("gcs_serial_delta_panel_scored", score=score, band=band)
        return [finding]
