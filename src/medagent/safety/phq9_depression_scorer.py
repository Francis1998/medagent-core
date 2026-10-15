"""Phq9DepressionScorer (research-only clinical score).

Advisory scorer closing the MDCalc / USPSTF PHQ-9 depression severity screen gap for
offline medical-ward agent pipelines.
Distinct from `EpworthSleepinessScorer` / `StopBangOsaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Phq9DepressionRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Phq9DepressionFactors:
    """Simplified Phq9DepressionScorer factors."""

    interest_ok: int = 0
    mood_ok: int = 0
    sleep_ok: int = 0
    energy_ok: int = 0
    appetite_ok: int = 0
    guilt_ok: int = 0
    concentration_ok: int = 0
    motor_ok: int = 0
    suicidality_ok: int = 0


class Phq9DepressionScorer:
    """Compute advisory Phq9DepressionRisk findings."""

    def check(self, factors: Phq9DepressionFactors) -> list[Phq9DepressionRisk]:
        """Return one advisory finding."""

        binaries = {
            "interest_ok": factors.interest_ok,
            "mood_ok": factors.mood_ok,
            "sleep_ok": factors.sleep_ok,
            "energy_ok": factors.energy_ok,
            "appetite_ok": factors.appetite_ok,
            "guilt_ok": factors.guilt_ok,
            "concentration_ok": factors.concentration_ok,
            "motor_ok": factors.motor_ok,
            "suicidality_ok": factors.suicidality_ok,
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
            "RESEARCH USE ONLY: Phq9DepressionScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Phq9DepressionRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("phq9_depression_scorer_scored", score=score, band=band)
        return [finding]
