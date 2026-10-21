"""ForresterClassScorer (research-only clinical score).

Advisory scorer closing the MDCalc / Killip-Forrester hemodynamic class screen gap for
offline medical-ward agent pipelines.
Distinct from `GraceAcsScorer` / `HeartScoreAcsScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ForresterClassRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ForresterClassFactors:
    """Simplified ForresterClassScorer factors."""

    pulmonary_congestion: int = 0
    peripheral_hypoperfusion: int = 0
    cardiogenic_shock_signs: int = 0
    elevated_filling_pressures: int = 0
    low_cardiac_index: int = 0
    vasopressor_support: int = 0


class ForresterClassScorer:
    """Compute advisory ForresterClassRisk findings."""

    def check(self, factors: ForresterClassFactors) -> list[ForresterClassRisk]:
        """Return one advisory finding."""

        binaries = {
            "pulmonary_congestion": factors.pulmonary_congestion,
            "peripheral_hypoperfusion": factors.peripheral_hypoperfusion,
            "cardiogenic_shock_signs": factors.cardiogenic_shock_signs,
            "elevated_filling_pressures": factors.elevated_filling_pressures,
            "low_cardiac_index": factors.low_cardiac_index,
            "vasopressor_support": factors.vasopressor_support,
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
            "RESEARCH USE ONLY: ForresterClassScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ForresterClassRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("forrester_class_scorer_scored", score=score, band=band)
        return [finding]
