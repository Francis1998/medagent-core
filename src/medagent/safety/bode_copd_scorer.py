"""BodeCopdScorer (research-only clinical score).

Advisory scorer closing the MDCalc / GOLD / EHR BODE COPD index score gap for
offline medical-ward agent pipelines.
Distinct from ``SofaOrganFailureScorer / Curb65PneumoniaScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import BodeCopdRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BodeCopdFactors:
    """Simplified BodeCopdScorer factors."""

    bmi_le_21: int = 0
    fev1_lt_65: int = 0
    mmrc_dyspnea_ge_2: int = 0
    six_min_walk_lt_350: int = 0
    exacerbation_history: int = 0
    oxygen_dependent: int = 0


class BodeCopdScorer:
    """Compute advisory BodeCopdRisk findings."""

    def check(self, factors: BodeCopdFactors) -> list[BodeCopdRisk]:
        """Return one advisory finding."""

        binaries = {
            "bmi_le_21": factors.bmi_le_21,
            "fev1_lt_65": factors.fev1_lt_65,
            "mmrc_dyspnea_ge_2": factors.mmrc_dyspnea_ge_2,
            "six_min_walk_lt_350": factors.six_min_walk_lt_350,
            "exacerbation_history": factors.exacerbation_history,
            "oxygen_dependent": factors.oxygen_dependent,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 2:
            band = "low"
            severity = Severity.LOW
        elif score <= 4:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: BodeCopdScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = BodeCopdRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("bode_copd_scorer_scored", score=score, band=band)
        return [finding]
