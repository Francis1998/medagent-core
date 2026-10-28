"""Abcd2SerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / ABCD2 serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `Abcd2TiaRiskScorer` / `NihssSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Abcd2SerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Abcd2SerialDeltaFactors:
    """Simplified Abcd2SerialDeltaPanel factors."""

    prior_abcd2_elevated: int = 0
    age_factor_new: int = 0
    bp_factor_new: int = 0
    clinical_features_worsened: int = 0
    duration_extended: int = 0
    diabetes_new: int = 0


class Abcd2SerialDeltaPanel:
    """Compute advisory Abcd2SerialDeltaRisk findings."""

    def check(self, factors: Abcd2SerialDeltaFactors) -> list[Abcd2SerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_abcd2_elevated": factors.prior_abcd2_elevated,
            "age_factor_new": factors.age_factor_new,
            "bp_factor_new": factors.bp_factor_new,
            "clinical_features_worsened": factors.clinical_features_worsened,
            "duration_extended": factors.duration_extended,
            "diabetes_new": factors.diabetes_new,
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
            "RESEARCH USE ONLY: Abcd2SerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Abcd2SerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("abcd2_serial_delta_panel_scored", score=score, band=band)
        return [finding]
