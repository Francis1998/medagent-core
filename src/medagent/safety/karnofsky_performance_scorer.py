"""KarnofskyPerformanceScorer (research-only clinical score).

Advisory scorer closing the MDCalc / Karnofsky Performance Status screen gap for
offline medical-ward agent pipelines.
Distinct from `EcogPerformanceScorer` / `BarthelAdlScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import KarnofskyPerformanceRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KarnofskyPerformanceFactors:
    """Simplified KarnofskyPerformanceScorer factors."""

    normal_activity: int = 0
    minor_symptoms: int = 0
    cares_for_self: int = 0
    needs_occasional_assistance: int = 0
    disabled: int = 0
    hospital_level_care: int = 0


class KarnofskyPerformanceScorer:
    """Compute advisory KarnofskyPerformanceRisk findings."""

    def check(self, factors: KarnofskyPerformanceFactors) -> list[KarnofskyPerformanceRisk]:
        """Return one advisory finding."""

        binaries = {
            "normal_activity": factors.normal_activity,
            "minor_symptoms": factors.minor_symptoms,
            "cares_for_self": factors.cares_for_self,
            "needs_occasional_assistance": factors.needs_occasional_assistance,
            "disabled": factors.disabled,
            "hospital_level_care": factors.hospital_level_care,
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
            "RESEARCH USE ONLY: KarnofskyPerformanceScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = KarnofskyPerformanceRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("karnofsky_performance_scorer_scored", score=score, band=band)
        return [finding]
