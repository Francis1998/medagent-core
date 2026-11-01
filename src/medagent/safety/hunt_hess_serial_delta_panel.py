"""HuntHessSerialDeltaPanel.

Advisory scorer closing the MDCalc / Hunt-Hess SAH serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `HuntHessSahScorer` / `OttawaSahSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import HuntHessSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HuntHessSerialDeltaFactors:
    """Simplified HuntHessSerialDeltaPanel factors."""

    prior_hunt_hess_elevated: int = 0
    consciousness_drop: int = 0
    focal_deficit_new: int = 0
    severe_headache_worsen: int = 0
    nuchal_rigidity_new: int = 0
    vasospasm_signal: int = 0


class HuntHessSerialDeltaPanel:
    """Compute advisory HuntHessSerialDeltaRisk findings."""

    def check(self, factors: HuntHessSerialDeltaFactors) -> list[HuntHessSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_hunt_hess_elevated": factors.prior_hunt_hess_elevated,
            "consciousness_drop": factors.consciousness_drop,
            "focal_deficit_new": factors.focal_deficit_new,
            "severe_headache_worsen": factors.severe_headache_worsen,
            "nuchal_rigidity_new": factors.nuchal_rigidity_new,
            "vasospasm_signal": factors.vasospasm_signal,
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
            "RESEARCH USE ONLY: HuntHessSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = HuntHessSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("hunt_hess_serial_delta_panel_scored", score=score, band=band)
        return [finding]
