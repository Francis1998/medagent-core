"""EcogPerformanceScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ECOG/WHO performance status screen gap for
offline medical-ward agent pipelines.
Distinct from `GcsNeurologicStatusScorer` / `ApacheIiLiteScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import EcogPerformanceRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EcogPerformanceFactors:
    """Simplified EcogPerformanceScorer factors."""

    restricted_activity: int = 0
    ambulatory_capable: int = 0
    limited_self_care: int = 0
    disabled: int = 0
    bedridden: int = 0
    hospitalized: int = 0


class EcogPerformanceScorer:
    """Compute advisory EcogPerformanceRisk findings."""

    def check(self, factors: EcogPerformanceFactors) -> list[EcogPerformanceRisk]:
        """Return one advisory finding."""

        binaries = {
            "restricted_activity": factors.restricted_activity,
            "ambulatory_capable": factors.ambulatory_capable,
            "limited_self_care": factors.limited_self_care,
            "disabled": factors.disabled,
            "bedridden": factors.bedridden,
            "hospitalized": factors.hospitalized,
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
            "RESEARCH USE ONLY: EcogPerformanceScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = EcogPerformanceRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ecog_performance_scorer_scored", score=score, band=band)
        return [finding]
