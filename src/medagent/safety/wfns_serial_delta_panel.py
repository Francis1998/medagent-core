"""WfnsSerialDeltaPanel.

Advisory scorer closing the MDCalc / WFNS SAH serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `WfnsSahScorer` / `HuntHessSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WfnsSerialDeltaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WfnsSerialDeltaFactors:
    """Simplified WfnsSerialDeltaPanel factors."""

    prior_wfns_elevated: int = 0
    gcs_drop: int = 0
    motor_deficit_new: int = 0
    aphasia_new: int = 0
    pupil_asymmetry_new: int = 0
    delayed_ischemia_signal: int = 0


class WfnsSerialDeltaPanel:
    """Compute advisory WfnsSerialDeltaRisk findings."""

    def check(self, factors: WfnsSerialDeltaFactors) -> list[WfnsSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_wfns_elevated": factors.prior_wfns_elevated,
            "gcs_drop": factors.gcs_drop,
            "motor_deficit_new": factors.motor_deficit_new,
            "aphasia_new": factors.aphasia_new,
            "pupil_asymmetry_new": factors.pupil_asymmetry_new,
            "delayed_ischemia_signal": factors.delayed_ischemia_signal,
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
            "RESEARCH USE ONLY: WfnsSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WfnsSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("wfns_serial_delta_panel_scored", score=score, band=band)
        return [finding]
