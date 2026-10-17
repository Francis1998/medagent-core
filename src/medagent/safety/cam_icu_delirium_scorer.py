"""CamIcuDeliriumScorer (research-only clinical score).

Advisory scorer closing the MDCalc / SCCM CAM-ICU delirium screen gap for
offline medical-ward agent pipelines.
Distinct from `GcsNeurologicStatusScorer` / `CiwaArWithdrawalScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CamIcuDeliriumRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CamIcuDeliriumFactors:
    """Simplified CamIcuDeliriumScorer factors."""

    acute_change: int = 0
    inattention: int = 0
    disorganized_thinking: int = 0
    altered_consciousness: int = 0


class CamIcuDeliriumScorer:
    """Compute advisory CamIcuDeliriumRisk findings."""

    def check(self, factors: CamIcuDeliriumFactors) -> list[CamIcuDeliriumRisk]:
        """Return one advisory finding."""

        binaries = {
            "acute_change": factors.acute_change,
            "inattention": factors.inattention,
            "disorganized_thinking": factors.disorganized_thinking,
            "altered_consciousness": factors.altered_consciousness,
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
            "RESEARCH USE ONLY: CamIcuDeliriumScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CamIcuDeliriumRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("cam_icu_delirium_scorer_scored", score=score, band=band)
        return [finding]
