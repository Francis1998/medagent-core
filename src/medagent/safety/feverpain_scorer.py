"""FeverPainScorer (research-only clinical score).

Advisory scorer closing the MDCalc / NICE FeverPAIN pharyngitis score gap for
offline medical-ward agent pipelines.
Distinct from `CentorStrepPharyngitisScorer` / `LightCriteriaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import FeverPainRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FeverPainFactors:
    """Simplified FeverPainScorer factors."""

    fever_in_past_24h: int = 0
    purulence: int = 0
    attend_rapidly: int = 0
    severely_inflamed_tonsils: int = 0
    no_cough_or_coryza: int = 0


class FeverPainScorer:
    """Compute advisory FeverPainRisk findings."""

    def check(self, factors: FeverPainFactors) -> list[FeverPainRisk]:
        """Return one advisory finding."""

        binaries = {
            "fever_in_past_24h": factors.fever_in_past_24h,
            "purulence": factors.purulence,
            "attend_rapidly": factors.attend_rapidly,
            "severely_inflamed_tonsils": factors.severely_inflamed_tonsils,
            "no_cough_or_coryza": factors.no_cough_or_coryza,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 3:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: FeverPainScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = FeverPainRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("feverpain_scorer_scored", score=score, band=band)
        return [finding]
