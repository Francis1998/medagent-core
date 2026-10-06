"""MewsScorer (research-only clinical score).

Advisory scorer closing the MDCalc / NICE / EHR MEWS gap for
offline medical-ward agent pipelines.
Distinct from ``News2EarlyWarningScorer / VitalsTriageChecker``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MewsRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MewsFactors:
    """Simplified MewsScorer factors."""

    rr_abnormal: int = 0
    hr_abnormal: int = 0
    sbp_abnormal: int = 0
    temp_abnormal: int = 0
    avpu_not_alert: int = 0


class MewsScorer:
    """Compute advisory MewsRisk findings."""

    def check(self, factors: MewsFactors) -> list[MewsRisk]:
        """Return one advisory finding."""

        binaries = {
            "rr_abnormal": factors.rr_abnormal,
            "hr_abnormal": factors.hr_abnormal,
            "sbp_abnormal": factors.sbp_abnormal,
            "temp_abnormal": factors.temp_abnormal,
            "avpu_not_alert": factors.avpu_not_alert,
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
            "RESEARCH USE ONLY: MewsScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MewsRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("mews_scorer_scored", score=score, band=band)
        return [finding]
