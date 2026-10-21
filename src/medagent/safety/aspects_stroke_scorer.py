"""AspectsStrokeScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ASPECTS early ischemic change screen gap for
offline medical-ward agent pipelines.
Distinct from `NihssStrokeScorer` / `CanadianCtHeadScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import AspectsStrokeRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AspectsStrokeFactors:
    """Simplified AspectsStrokeScorer factors."""

    mca_cortical_loss: int = 0
    insula_ribbon_loss: int = 0
    lentiform_hypodensity: int = 0
    caudate_hypodensity: int = 0
    internal_capsule_loss: int = 0
    posterior_mca_loss: int = 0


class AspectsStrokeScorer:
    """Compute advisory AspectsStrokeRisk findings."""

    def check(self, factors: AspectsStrokeFactors) -> list[AspectsStrokeRisk]:
        """Return one advisory finding."""

        binaries = {
            "mca_cortical_loss": factors.mca_cortical_loss,
            "insula_ribbon_loss": factors.insula_ribbon_loss,
            "lentiform_hypodensity": factors.lentiform_hypodensity,
            "caudate_hypodensity": factors.caudate_hypodensity,
            "internal_capsule_loss": factors.internal_capsule_loss,
            "posterior_mca_loss": factors.posterior_mca_loss,
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
            "RESEARCH USE ONLY: AspectsStrokeScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = AspectsStrokeRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("aspects_stroke_scorer_scored", score=score, band=band)
        return [finding]
