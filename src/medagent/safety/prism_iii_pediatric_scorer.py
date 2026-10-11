"""PrismIiiPediatricScorer (research-only clinical score).

Advisory scorer closing the MDCalc / PICU PRISM III pediatric ICU score gap for
offline medical-ward agent pipelines.
Distinct from `PewsEarlyWarningScorer / ApacheIiLiteScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PrismIiiPediatricRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PrismIiiPediatricFactors:
    """Simplified PrismIiiPediatricScorer factors."""

    cardio_ok: int = 0
    neuro_ok: int = 0
    resp_ok: int = 0
    metab_ok: int = 0


class PrismIiiPediatricScorer:
    """Compute advisory PrismIiiPediatricRisk findings."""

    def check(self, factors: PrismIiiPediatricFactors) -> list[PrismIiiPediatricRisk]:
        """Return one advisory finding."""

        binaries = {
            "cardio_ok": factors.cardio_ok,
            "neuro_ok": factors.neuro_ok,
            "resp_ok": factors.resp_ok,
            "metab_ok": factors.metab_ok,
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
            "RESEARCH USE ONLY: PrismIiiPediatricScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PrismIiiPediatricRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("prism_iii_pediatric_scorer_scored", score=score, band=band)
        return [finding]
