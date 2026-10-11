"""MaddreyDiscriminantScorer (research-only clinical score).

Advisory scorer closing the MDCalc Maddrey discriminant function for alcoholic hepatitis gap for
offline medical-ward agent pipelines.
Distinct from `MeldNaScorer / ChildPughLiverSeverityScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MaddreyDiscriminantRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MaddreyDiscriminantFactors:
    """Simplified MaddreyDiscriminantScorer factors."""

    pt_ok: int = 0
    bili_ok: int = 0
    enceph_ok: int = 0
    ascites_ok: int = 0


class MaddreyDiscriminantScorer:
    """Compute advisory MaddreyDiscriminantRisk findings."""

    def check(self, factors: MaddreyDiscriminantFactors) -> list[MaddreyDiscriminantRisk]:
        """Return one advisory finding."""

        binaries = {
            "pt_ok": factors.pt_ok,
            "bili_ok": factors.bili_ok,
            "enceph_ok": factors.enceph_ok,
            "ascites_ok": factors.ascites_ok,
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
            "RESEARCH USE ONLY: MaddreyDiscriminantScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MaddreyDiscriminantRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("maddrey_discriminant_scorer_scored", score=score, band=band)
        return [finding]
