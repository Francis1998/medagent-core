"""NexusCspineScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACEP / EHR NEXUS C-spine rule gap for
offline medical-ward agent pipelines.
Distinct from ``CanadianCspineRuleScorer / OttawaAnkleRuleScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import NexusCspineRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NexusCspineFactors:
    """Simplified NexusCspineScorer factors."""

    midline_tenderness: int = 0
    altered_alertness: int = 0
    intoxication: int = 0
    focal_neuro_deficit: int = 0
    distracting_injury: int = 0


class NexusCspineScorer:
    """Compute advisory NexusCspineRisk findings."""

    def check(self, factors: NexusCspineFactors) -> list[NexusCspineRisk]:
        """Return one advisory finding."""

        binaries = {
            "midline_tenderness": factors.midline_tenderness,
            "altered_alertness": factors.altered_alertness,
            "intoxication": factors.intoxication,
            "focal_neuro_deficit": factors.focal_neuro_deficit,
            "distracting_injury": factors.distracting_injury,
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
            "RESEARCH USE ONLY: NexusCspineScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = NexusCspineRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("nexus_cspine_scorer_scored", score=score, band=band)
        return [finding]
