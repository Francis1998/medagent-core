"""FourAtDeliriumScorer (research-only clinical score).

Advisory scorer closing the MDCalc / 4AT rapid delirium screen gap for
offline medical-ward agent pipelines.
Distinct from `CamIcuDeliriumScorer` / `CiwaArWithdrawalScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import FourAtDeliriumRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FourAtDeliriumFactors:
    """Simplified FourAtDeliriumScorer factors."""

    alertness_change: int = 0
    amt4_errors: int = 0
    attention_months: int = 0
    acute_change_fluctuation: int = 0
    collateral_confusion: int = 0
    hospitalized: int = 0


class FourAtDeliriumScorer:
    """Compute advisory FourAtDeliriumRisk findings."""

    def check(self, factors: FourAtDeliriumFactors) -> list[FourAtDeliriumRisk]:
        """Return one advisory finding."""

        binaries = {
            "alertness_change": factors.alertness_change,
            "amt4_errors": factors.amt4_errors,
            "attention_months": factors.attention_months,
            "acute_change_fluctuation": factors.acute_change_fluctuation,
            "collateral_confusion": factors.collateral_confusion,
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
            "RESEARCH USE ONLY: FourAtDeliriumScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = FourAtDeliriumRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("four_at_delirium_scorer_scored", score=score, band=band)
        return [finding]
