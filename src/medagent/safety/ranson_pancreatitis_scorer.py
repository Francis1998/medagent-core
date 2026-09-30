"""RansonPancreatitisScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACG / EHR Ranson pancreatitis criteria gap for
offline medical-ward agent pipelines.
Distinct from ``AlvaradoAppendicitisScorer / SofaOrganFailureScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RansonPancreatitisRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RansonPancreatitisFactors:
    """Simplified RansonPancreatitisScorer factors."""

    age_gt_55: int = 0
    wbc_gt_16: int = 0
    glucose_gt_200: int = 0
    ldh_gt_350: int = 0
    ast_gt_250: int = 0
    hct_drop_gt_10: int = 0
    bun_rise_gt_5: int = 0
    calcium_lt_8: int = 0
    po2_lt_60: int = 0
    base_deficit_gt_4: int = 0
    fluid_sequestration_gt_6l: int = 0


class RansonPancreatitisScorer:
    """Compute advisory RansonPancreatitisRisk findings."""

    def check(self, factors: RansonPancreatitisFactors) -> list[RansonPancreatitisRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_gt_55": factors.age_gt_55,
            "wbc_gt_16": factors.wbc_gt_16,
            "glucose_gt_200": factors.glucose_gt_200,
            "ldh_gt_350": factors.ldh_gt_350,
            "ast_gt_250": factors.ast_gt_250,
            "hct_drop_gt_10": factors.hct_drop_gt_10,
            "bun_rise_gt_5": factors.bun_rise_gt_5,
            "calcium_lt_8": factors.calcium_lt_8,
            "po2_lt_60": factors.po2_lt_60,
            "base_deficit_gt_4": factors.base_deficit_gt_4,
            "fluid_sequestration_gt_6l": factors.fluid_sequestration_gt_6l,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 2:
            band = "mild"
            severity = Severity.LOW
        elif score <= 4:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "severe"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: RansonPancreatitisScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RansonPancreatitisRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ranson_pancreatitis_scorer_scored", score=score, band=band)
        return [finding]
