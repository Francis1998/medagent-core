"""WellsDvtProbabilityScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACCP / EHR Wells DVT probability gap for
offline medical-ward agent pipelines.
Distinct from ``WellsPeProbabilityScorer / CapriniVteRiskScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full Wells DVT chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WellsDvtProbability

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WellsDvtFactors:
    """Simplified Wells DVT-style factors (1 point each when present)."""

    active_cancer: int = 0
    paralysis_or_plaster: int = 0
    bedridden_or_surgery: int = 0
    tenderness_deep_veins: int = 0
    entire_leg_swollen: int = 0
    calf_swelling_3cm: int = 0
    pitting_edema: int = 0
    collateral_veins: int = 0
    previous_dvt: int = 0
    alternative_diagnosis_likely: int = 0  # subtracts 2 when present


class WellsDvtProbabilityScorer:
    """Compute advisory WellsDvtProbability findings."""

    def check(self, factors: WellsDvtFactors) -> list[WellsDvtProbability]:
        """Return one advisory finding."""

        binaries = {
            "active_cancer": factors.active_cancer,
            "paralysis_or_plaster": factors.paralysis_or_plaster,
            "bedridden_or_surgery": factors.bedridden_or_surgery,
            "tenderness_deep_veins": factors.tenderness_deep_veins,
            "entire_leg_swollen": factors.entire_leg_swollen,
            "calf_swelling_3cm": factors.calf_swelling_3cm,
            "pitting_edema": factors.pitting_edema,
            "collateral_veins": factors.collateral_veins,
            "previous_dvt": factors.previous_dvt,
            "alternative_diagnosis_likely": factors.alternative_diagnosis_likely,
        }
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        score = sum(v for k, v in binaries.items() if k != "alternative_diagnosis_likely")
        if factors.alternative_diagnosis_likely:
            score -= 2
        positive = [k for k, v in binaries.items() if v > 0]
        if score >= 3:
            band = "high"
            severity = Severity.HIGH
        elif score >= 1:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: WellsDvtProbabilityScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WellsDvtProbability(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("wells_dvt_probability_scorer_scored", score=score, band=band)
        return [finding]
