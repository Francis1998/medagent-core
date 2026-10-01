"""PecarnHeadTraumaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACEP / EHR PECARN pediatric head trauma score gap for
offline medical-ward agent pipelines.
Distinct from ``CanadianCspineRuleScorer / FallRiskChecker``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PecarnHeadTraumaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PecarnHeadTraumaFactors:
    """Simplified PecarnHeadTraumaScorer factors."""

    altered_mental_status: int = 0
    skull_fracture_suspect: int = 0
    severe_mechanism: int = 0
    vomiting_or_headache: int = 0
    basilar_signs: int = 0
    acting_abnormally: int = 0


class PecarnHeadTraumaScorer:
    """Compute advisory PecarnHeadTraumaRisk findings."""

    def check(self, factors: PecarnHeadTraumaFactors) -> list[PecarnHeadTraumaRisk]:
        """Return one advisory finding."""

        binaries = {
            "altered_mental_status": factors.altered_mental_status,
            "skull_fracture_suspect": factors.skull_fracture_suspect,
            "severe_mechanism": factors.severe_mechanism,
            "vomiting_or_headache": factors.vomiting_or_headache,
            "basilar_signs": factors.basilar_signs,
            "acting_abnormally": factors.acting_abnormally,
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
            "RESEARCH USE ONLY: PecarnHeadTraumaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PecarnHeadTraumaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("pecarn_head_trauma_scorer_scored", score=score, band=band)
        return [finding]
