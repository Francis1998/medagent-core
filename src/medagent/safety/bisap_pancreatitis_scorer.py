"""BisapPancreatitisScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACG BISAP pancreatitis severity screen gap for
offline medical-ward agent pipelines.
Distinct from `RansonPancreatitisScorer` / `MaddreyDiscriminantScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import BisapPancreatitisRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BisapPancreatitisFactors:
    """Simplified BisapPancreatitisScorer factors."""

    bun_ok: int = 0
    impaired_mental_ok: int = 0
    sirs_ok: int = 0
    age_ok: int = 0
    pleural_effusion_ok: int = 0


class BisapPancreatitisScorer:
    """Compute advisory BisapPancreatitisRisk findings."""

    def check(self, factors: BisapPancreatitisFactors) -> list[BisapPancreatitisRisk]:
        """Return one advisory finding."""

        binaries = {
            "bun_ok": factors.bun_ok,
            "impaired_mental_ok": factors.impaired_mental_ok,
            "sirs_ok": factors.sirs_ok,
            "age_ok": factors.age_ok,
            "pleural_effusion_ok": factors.pleural_effusion_ok,
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
            "RESEARCH USE ONLY: BisapPancreatitisScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = BisapPancreatitisRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("bisap_pancreatitis_scorer_scored", score=score, band=band)
        return [finding]
