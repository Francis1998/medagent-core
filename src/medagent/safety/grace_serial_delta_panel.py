"""GraceSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / GRACE ACS serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `GraceAcsScorer` / `HeartSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import GraceSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GraceSerialDeltaFactors:
    """Simplified GraceSerialDeltaPanel factors."""

    prior_grace_elevated: int = 0
    age_factor_new: int = 0
    heart_rate_worsened: int = 0
    systolic_bp_dropped: int = 0
    creatinine_rise: int = 0
    killip_class_worsened: int = 0


class GraceSerialDeltaPanel:
    """Compute advisory GraceSerialDeltaRisk findings."""

    def check(self, factors: GraceSerialDeltaFactors) -> list[GraceSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_grace_elevated": factors.prior_grace_elevated,
            "age_factor_new": factors.age_factor_new,
            "heart_rate_worsened": factors.heart_rate_worsened,
            "systolic_bp_dropped": factors.systolic_bp_dropped,
            "creatinine_rise": factors.creatinine_rise,
            "killip_class_worsened": factors.killip_class_worsened,
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
            "RESEARCH USE ONLY: GraceSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = GraceSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("grace_serial_delta_panel_scored", score=score, band=band)
        return [finding]
