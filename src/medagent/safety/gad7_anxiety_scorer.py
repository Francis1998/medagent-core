"""Gad7AnxietyScorer (research-only clinical score).

Advisory scorer closing the MDCalc / USPSTF GAD-7 anxiety severity screen gap for
offline medical-ward agent pipelines.
Distinct from `Phq9DepressionScorer` / `EpworthSleepinessScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Gad7AnxietyRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Gad7AnxietyFactors:
    """Simplified Gad7AnxietyScorer factors."""

    nervous_ok: int = 0
    control_worry_ok: int = 0
    worry_ok: int = 0
    relax_ok: int = 0
    restless_ok: int = 0
    irritable_ok: int = 0
    afraid_ok: int = 0


class Gad7AnxietyScorer:
    """Compute advisory Gad7AnxietyRisk findings."""

    def check(self, factors: Gad7AnxietyFactors) -> list[Gad7AnxietyRisk]:
        """Return one advisory finding."""

        binaries = {
            "nervous_ok": factors.nervous_ok,
            "control_worry_ok": factors.control_worry_ok,
            "worry_ok": factors.worry_ok,
            "relax_ok": factors.relax_ok,
            "restless_ok": factors.restless_ok,
            "irritable_ok": factors.irritable_ok,
            "afraid_ok": factors.afraid_ok,
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
            "RESEARCH USE ONLY: Gad7AnxietyScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Gad7AnxietyRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("gad7_anxiety_scorer_scored", score=score, band=band)
        return [finding]
