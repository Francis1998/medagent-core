"""PewsEarlyWarningScorer (research-only clinical score).

Advisory scorer closing the MDCalc / RCN PEWS pediatric early warning score gap for
offline medical-ward agent pipelines.
Distinct from `News2EarlyWarningScorer` / `MewsScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PewsEarlyWarningRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PewsEarlyWarningFactors:
    """Simplified PewsEarlyWarningScorer factors."""

    behavior_ok: int = 0
    cardiovascular_ok: int = 0
    respiratory_ok: int = 0
    nebulizer_ok: int = 0
    vomiting_ok: int = 0


class PewsEarlyWarningScorer:
    """Compute advisory PewsEarlyWarningRisk findings."""

    def check(self, factors: PewsEarlyWarningFactors) -> list[PewsEarlyWarningRisk]:
        """Return one advisory finding."""

        binaries = {
            "behavior_ok": factors.behavior_ok,
            "cardiovascular_ok": factors.cardiovascular_ok,
            "respiratory_ok": factors.respiratory_ok,
            "nebulizer_ok": factors.nebulizer_ok,
            "vomiting_ok": factors.vomiting_ok,
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
            "RESEARCH USE ONLY: PewsEarlyWarningScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PewsEarlyWarningRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("pews_early_warning_scorer_scored", score=score, band=band)
        return [finding]
