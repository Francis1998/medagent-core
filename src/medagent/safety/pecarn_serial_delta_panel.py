"""PecarnSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / PECARN pediatric head trauma serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `PecarnHeadTraumaScorer` / `CanadianCtHeadSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PecarnSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PecarnSerialDeltaFactors:
    """Simplified PecarnSerialDeltaPanel factors."""

    prior_pecarn_elevated: int = 0
    gcs_drop: int = 0
    altered_mental_new: int = 0
    palpable_skull_fracture_new: int = 0
    severe_mechanism_new: int = 0
    acting_abnormal_new: int = 0


class PecarnSerialDeltaPanel:
    """Compute advisory PecarnSerialDeltaRisk findings."""

    def check(self, factors: PecarnSerialDeltaFactors) -> list[PecarnSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_pecarn_elevated": factors.prior_pecarn_elevated,
            "gcs_drop": factors.gcs_drop,
            "altered_mental_new": factors.altered_mental_new,
            "palpable_skull_fracture_new": factors.palpable_skull_fracture_new,
            "severe_mechanism_new": factors.severe_mechanism_new,
            "acting_abnormal_new": factors.acting_abnormal_new,
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
            "RESEARCH USE ONLY: PecarnSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PecarnSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("pecarn_serial_delta_panel_scored", score=score, band=band)
        return [finding]
