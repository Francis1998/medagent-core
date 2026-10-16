"""BradenPressureScorer (research-only clinical score).

Advisory scorer closing the MDCalc / NPUAP Braden pressure-injury risk screen gap for
offline medical-ward agent pipelines.
Distinct from `News2EarlyWarningScorer` / `SofaOrganFailureScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import BradenPressureRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BradenPressureFactors:
    """Simplified BradenPressureScorer factors."""

    sensory_ok: int = 0
    moisture_ok: int = 0
    activity_ok: int = 0
    mobility_ok: int = 0
    nutrition_ok: int = 0
    friction_ok: int = 0


class BradenPressureScorer:
    """Compute advisory BradenPressureRisk findings."""

    def check(self, factors: BradenPressureFactors) -> list[BradenPressureRisk]:
        """Return one advisory finding."""

        binaries = {
            "sensory_ok": factors.sensory_ok,
            "moisture_ok": factors.moisture_ok,
            "activity_ok": factors.activity_ok,
            "mobility_ok": factors.mobility_ok,
            "nutrition_ok": factors.nutrition_ok,
            "friction_ok": factors.friction_ok,
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
            "RESEARCH USE ONLY: BradenPressureScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = BradenPressureRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("braden_pressure_scorer_scored", score=score, band=band)
        return [finding]
