"""StopBangOsaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ASA STOP-BANG OSA screen gap for
offline medical-ward agent pipelines.
Distinct from `EpworthSleepiness / MallampatiAirwayScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, StopBangOsaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StopBangOsaFactors:
    """Simplified StopBangOsaScorer factors."""

    snore_ok: int = 0
    tired_ok: int = 0
    observed_ok: int = 0
    pressure_ok: int = 0


class StopBangOsaScorer:
    """Compute advisory StopBangOsaRisk findings."""

    def check(self, factors: StopBangOsaFactors) -> list[StopBangOsaRisk]:
        """Return one advisory finding."""

        binaries = {
            "snore_ok": factors.snore_ok,
            "tired_ok": factors.tired_ok,
            "observed_ok": factors.observed_ok,
            "pressure_ok": factors.pressure_ok,
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
            "RESEARCH USE ONLY: StopBangOsaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = StopBangOsaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("stop_bang_osa_scorer_scored", score=score, band=band)
        return [finding]
