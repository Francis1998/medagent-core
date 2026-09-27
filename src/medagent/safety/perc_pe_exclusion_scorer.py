"""PercPeExclusionScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACEP / EHR PERC PE rule-out gap for
offline medical-ward agent pipelines.
Distinct from ``WellsPeProbabilityScorer / PaduaVteRiskScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full PERC chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PercPeExclusionRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PercPeFactors:
    """Simplified PERC rule factors (any positive fails rule-out)."""

    age_ge_50: int = 0
    hr_ge_100: int = 0
    o2_sat_lt_95: int = 0
    unilateral_leg_swelling: int = 0
    hemoptysis: int = 0
    recent_surgery_or_trauma: int = 0
    prior_pe_or_dvt: int = 0
    hormone_use: int = 0


class PercPeExclusionScorer:
    """Compute advisory PercPeExclusionRisk findings."""

    def check(self, factors: PercPeFactors) -> list[PercPeExclusionRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_50": factors.age_ge_50,
            "hr_ge_100": factors.hr_ge_100,
            "o2_sat_lt_95": factors.o2_sat_lt_95,
            "unilateral_leg_swelling": factors.unilateral_leg_swelling,
            "hemoptysis": factors.hemoptysis,
            "recent_surgery_or_trauma": factors.recent_surgery_or_trauma,
            "prior_pe_or_dvt": factors.prior_pe_or_dvt,
            "hormone_use": factors.hormone_use,
        }
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]
        if score == 0:
            band = "rule_out"
            severity = Severity.LOW
        elif score == 1:
            band = "near_miss"
            severity = Severity.MODERATE
        else:
            band = "not_ruled_out"
            severity = Severity.HIGH
        rationale = (
            "RESEARCH USE ONLY: PercPeExclusionScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PercPeExclusionRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("perc_pe_exclusion_scorer_scored", score=score, band=band)
        return [finding]
