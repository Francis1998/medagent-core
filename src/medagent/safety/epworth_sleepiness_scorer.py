"""EpworthSleepinessScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AASM Epworth Sleepiness Scale screen gap for
offline medical-ward agent pipelines.
Distinct from `StopBangOsaScorer` / `MallampatiAirwayScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import EpworthSleepinessRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EpworthSleepinessFactors:
    """Simplified EpworthSleepinessScorer factors."""

    sitting_ok: int = 0
    watching_tv_ok: int = 0
    passenger_ok: int = 0
    lying_down_ok: int = 0


class EpworthSleepinessScorer:
    """Compute advisory EpworthSleepinessRisk findings."""

    def check(self, factors: EpworthSleepinessFactors) -> list[EpworthSleepinessRisk]:
        """Return one advisory finding."""

        binaries = {
            "sitting_ok": factors.sitting_ok,
            "watching_tv_ok": factors.watching_tv_ok,
            "passenger_ok": factors.passenger_ok,
            "lying_down_ok": factors.lying_down_ok,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 2:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: EpworthSleepinessScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = EpworthSleepinessRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("epworth_sleepiness_scorer_scored", score=score, band=band)
        return [finding]
