"""Fib4LiverScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AASLD FIB-4 liver fibrosis screen gap for
offline medical-ward agent pipelines.
Distinct from `ChildPughLiverSeverityScorer` / `MeldNaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Fib4LiverRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Fib4LiverFactors:
    """Simplified Fib4LiverScorer factors."""

    age_ok: int = 0
    ast_ok: int = 0
    alt_ok: int = 0
    platelet_ok: int = 0


class Fib4LiverScorer:
    """Compute advisory Fib4LiverRisk findings."""

    def check(self, factors: Fib4LiverFactors) -> list[Fib4LiverRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ok": factors.age_ok,
            "ast_ok": factors.ast_ok,
            "alt_ok": factors.alt_ok,
            "platelet_ok": factors.platelet_ok,
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
            "RESEARCH USE ONLY: Fib4LiverScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Fib4LiverRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("fib4_liver_scorer_scored", score=score, band=band)
        return [finding]
