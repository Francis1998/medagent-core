"""RansonSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Ranson serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `RansonPancreatitisScorer` / `BisapPancreatitisScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RansonSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RansonSerialDeltaFactors:
    """Simplified RansonSerialDeltaPanel factors."""

    prior_ranson_elevated: int = 0
    wbc_up: int = 0
    glucose_up: int = 0
    ldh_up: int = 0
    ast_up: int = 0
    calcium_down: int = 0


class RansonSerialDeltaPanel:
    """Compute advisory RansonSerialDeltaRisk findings."""

    def check(self, factors: RansonSerialDeltaFactors) -> list[RansonSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_ranson_elevated": factors.prior_ranson_elevated,
            "wbc_up": factors.wbc_up,
            "glucose_up": factors.glucose_up,
            "ldh_up": factors.ldh_up,
            "ast_up": factors.ast_up,
            "calcium_down": factors.calcium_down,
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
            "RESEARCH USE ONLY: RansonSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RansonSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ranson_serial_delta_panel_scored", score=score, band=band)
        return [finding]
