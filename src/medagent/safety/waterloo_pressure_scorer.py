"""WaterlooPressureScorer (research-only clinical score).

Advisory scorer closing the MDCalc / Waterloo pressure-injury risk screen gap for
offline medical-ward agent pipelines.
Distinct from `BradenPressureScorer` / `MorseFallScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WaterlooPressureRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WaterlooPressureFactors:
    """Simplified WaterlooPressureScorer factors."""

    build_risk: int = 0
    skin_risk: int = 0
    continence_risk: int = 0
    mobility_risk: int = 0
    appetite_risk: int = 0
    special_risk: int = 0


class WaterlooPressureScorer:
    """Compute advisory WaterlooPressureRisk findings."""

    def check(self, factors: WaterlooPressureFactors) -> list[WaterlooPressureRisk]:
        """Return one advisory finding."""

        binaries = {
            "build_risk": factors.build_risk,
            "skin_risk": factors.skin_risk,
            "continence_risk": factors.continence_risk,
            "mobility_risk": factors.mobility_risk,
            "appetite_risk": factors.appetite_risk,
            "special_risk": factors.special_risk,
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
            "RESEARCH USE ONLY: WaterlooPressureScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WaterlooPressureRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("waterloo_pressure_scorer_scored", score=score, band=band)
        return [finding]
