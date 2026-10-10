"""SirsCriteriaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / SCCM SIRS criteria screen gap for
offline medical-ward agent pipelines.
Distinct from `QsofaSepsisScreenScorer` / `SofaOrganFailureScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, SirsCriteriaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SirsCriteriaFactors:
    """Simplified SirsCriteriaScorer factors."""

    temp_ok: int = 0
    hr_ok: int = 0
    rr_ok: int = 0
    wbc_ok: int = 0


class SirsCriteriaScorer:
    """Compute advisory SirsCriteriaRisk findings."""

    def check(self, factors: SirsCriteriaFactors) -> list[SirsCriteriaRisk]:
        """Return one advisory finding."""

        binaries = {
            "temp_ok": factors.temp_ok,
            "hr_ok": factors.hr_ok,
            "rr_ok": factors.rr_ok,
            "wbc_ok": factors.wbc_ok,
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
            "RESEARCH USE ONLY: SirsCriteriaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = SirsCriteriaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("sirs_criteria_scorer_scored", score=score, band=band)
        return [finding]
