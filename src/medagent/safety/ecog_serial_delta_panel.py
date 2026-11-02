"""EcogSerialDeltaPanel.

Advisory scorer closing the MDCalc / ECOG performance serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `EcogPerformanceScorer` / `KarnofskyPerformanceScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import EcogSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EcogSerialDeltaFactors:
    """Simplified EcogSerialDeltaPanel factors."""

    prior_ecog_elevated: int = 0
    ambulation_decline: int = 0
    self_care_loss: int = 0
    work_capacity_drop: int = 0
    bedbound_signal: int = 0
    symptom_burden_rise: int = 0


class EcogSerialDeltaPanel:
    """Compute advisory EcogSerialDeltaRisk findings."""

    def check(self, factors: EcogSerialDeltaFactors) -> list[EcogSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_ecog_elevated": factors.prior_ecog_elevated,
            "ambulation_decline": factors.ambulation_decline,
            "self_care_loss": factors.self_care_loss,
            "work_capacity_drop": factors.work_capacity_drop,
            "bedbound_signal": factors.bedbound_signal,
            "symptom_burden_rise": factors.symptom_burden_rise,
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
            "RESEARCH USE ONLY: EcogSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = EcogSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ecog_serial_delta_panel_scored", score=score, band=band)
        return [finding]
