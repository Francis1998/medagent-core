"""WfnsSahScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA / EHR WFNS SAH grade gap for
offline medical-ward agent pipelines.
Distinct from ``HuntHessSahScorer / NihssStrokeScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WfnsSahRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WfnsSahFactors:
    """Simplified WfnsSahScorer factors."""

    grade_ge_3: int = 0
    motor_deficit: int = 0
    gcs_le_12: int = 0
    gcs_le_6: int = 0


class WfnsSahScorer:
    """Compute advisory WfnsSahRisk findings."""

    def check(self, factors: WfnsSahFactors) -> list[WfnsSahRisk]:
        """Return one advisory finding."""

        binaries = {
            "grade_ge_3": factors.grade_ge_3,
            "motor_deficit": factors.motor_deficit,
            "gcs_le_12": factors.gcs_le_12,
            "gcs_le_6": factors.gcs_le_6,
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
            "RESEARCH USE ONLY: WfnsSahScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WfnsSahRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("wfns_sah_scorer_scored", score=score, band=band)
        return [finding]
