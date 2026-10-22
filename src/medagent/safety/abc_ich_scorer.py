"""AbcIchScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ABC ICH volume/severity screen gap for
offline medical-ward agent pipelines.
Distinct from `IchScoreScorer` / `HuntHessSahScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import AbcIchRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AbcIchFactors:
    """Simplified AbcIchScorer factors."""

    large_volume: int = 0
    intraventricular_extension: int = 0
    infratentorial_origin: int = 0
    gcs_depressed: int = 0
    anticoagulation: int = 0
    age_high: int = 0


class AbcIchScorer:
    """Compute advisory AbcIchRisk findings."""

    def check(self, factors: AbcIchFactors) -> list[AbcIchRisk]:
        """Return one advisory finding."""

        binaries = {
            "large_volume": factors.large_volume,
            "intraventricular_extension": factors.intraventricular_extension,
            "infratentorial_origin": factors.infratentorial_origin,
            "gcs_depressed": factors.gcs_depressed,
            "anticoagulation": factors.anticoagulation,
            "age_high": factors.age_high,
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
            "RESEARCH USE ONLY: AbcIchScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = AbcIchRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("abc_ich_scorer_scored", score=score, band=band)
        return [finding]
