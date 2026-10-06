"""FisherGradeScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA Fisher grade gap for
offline medical-ward agent pipelines.
Distinct from ``HuntHessSahScorer / WfnsSahScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import FisherGradeRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FisherGradeFactors:
    """Simplified FisherGradeScorer factors."""

    diffuse_blood: int = 0
    localized_clot: int = 0
    vertical_layer_ge_1mm: int = 0
    intraparenchymal_or_ivh: int = 0


class FisherGradeScorer:
    """Compute advisory FisherGradeRisk findings."""

    def check(self, factors: FisherGradeFactors) -> list[FisherGradeRisk]:
        """Return one advisory finding."""

        binaries = {
            "diffuse_blood": factors.diffuse_blood,
            "localized_clot": factors.localized_clot,
            "vertical_layer_ge_1mm": factors.vertical_layer_ge_1mm,
            "intraparenchymal_or_ivh": factors.intraparenchymal_or_ivh,
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
            "RESEARCH USE ONLY: FisherGradeScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = FisherGradeRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("fisher_grade_scorer_scored", score=score, band=band)
        return [finding]
