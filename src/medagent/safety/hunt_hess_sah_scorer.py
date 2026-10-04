"""HuntHessSahScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA / EHR Hunt-Hess SAH grade gap for
offline medical-ward agent pipelines.
Distinct from ``NihssStrokeScorer / GcsNeurologicStatusScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import HuntHessSahRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HuntHessSahFactors:
    """Simplified HuntHessSahScorer factors."""

    grade_1_asymptomatic: int = 0
    grade_2_cn_palsy: int = 0
    grade_3_drowsy: int = 0
    grade_4_stupor: int = 0
    grade_5_coma: int = 0


class HuntHessSahScorer:
    """Compute advisory HuntHessSahRisk findings."""

    def check(self, factors: HuntHessSahFactors) -> list[HuntHessSahRisk]:
        """Return one advisory finding."""

        binaries = {
            "grade_1_asymptomatic": factors.grade_1_asymptomatic,
            "grade_2_cn_palsy": factors.grade_2_cn_palsy,
            "grade_3_drowsy": factors.grade_3_drowsy,
            "grade_4_stupor": factors.grade_4_stupor,
            "grade_5_coma": factors.grade_5_coma,
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
            "RESEARCH USE ONLY: HuntHessSahScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = HuntHessSahRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("hunt_hess_sah_scorer_scored", score=score, band=band)
        return [finding]
