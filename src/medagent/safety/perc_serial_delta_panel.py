"""PercSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / PERC serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `PercPeExclusionScorer` / `WellsPeSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PercSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PercSerialDeltaFactors:
    """Simplified PercSerialDeltaPanel factors."""

    prior_perc_positive: int = 0
    new_perc_factor: int = 0
    hr_rise: int = 0
    spo2_drop: int = 0
    hemoptysis_onset: int = 0
    estrogen_exposure: int = 0


class PercSerialDeltaPanel:
    """Compute advisory PercSerialDeltaRisk findings."""

    def check(self, factors: PercSerialDeltaFactors) -> list[PercSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_perc_positive": factors.prior_perc_positive,
            "new_perc_factor": factors.new_perc_factor,
            "hr_rise": factors.hr_rise,
            "spo2_drop": factors.spo2_drop,
            "hemoptysis_onset": factors.hemoptysis_onset,
            "estrogen_exposure": factors.estrogen_exposure,
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
            "RESEARCH USE ONLY: PercSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PercSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("perc_serial_delta_panel_scored", score=score, band=band)
        return [finding]
