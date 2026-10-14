"""ShockIndexScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA Shock Index screen gap for
offline medical-ward agent pipelines.
Distinct from `QsofaSepsisScreenScorer` / `PhoenixSepsisCriteriaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, ShockIndexRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ShockIndexFactors:
    """Simplified ShockIndexScorer factors."""

    hr_ok: int = 0
    sbp_ok: int = 0
    altered_ok: int = 0
    lactate_ok: int = 0


class ShockIndexScorer:
    """Compute advisory ShockIndexRisk findings."""

    def check(self, factors: ShockIndexFactors) -> list[ShockIndexRisk]:
        """Return one advisory finding."""

        binaries = {
            "hr_ok": factors.hr_ok,
            "sbp_ok": factors.sbp_ok,
            "altered_ok": factors.altered_ok,
            "lactate_ok": factors.lactate_ok,
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
            "RESEARCH USE ONLY: ShockIndexScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ShockIndexRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("shock_index_scorer_scored", score=score, band=band)
        return [finding]
