"""MeldNaSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / MELD-Na serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `MeldNaScorer` / `ChildPughLiverSeverityScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MeldNaSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MeldNaSerialDeltaFactors:
    """Simplified MeldNaSerialDeltaPanel factors."""

    prior_meld_elevated: int = 0
    creatinine_up: int = 0
    bilirubin_up: int = 0
    inr_up: int = 0
    sodium_down: int = 0
    dialysis_new: int = 0


class MeldNaSerialDeltaPanel:
    """Compute advisory MeldNaSerialDeltaRisk findings."""

    def check(self, factors: MeldNaSerialDeltaFactors) -> list[MeldNaSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_meld_elevated": factors.prior_meld_elevated,
            "creatinine_up": factors.creatinine_up,
            "bilirubin_up": factors.bilirubin_up,
            "inr_up": factors.inr_up,
            "sodium_down": factors.sodium_down,
            "dialysis_new": factors.dialysis_new,
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
            "RESEARCH USE ONLY: MeldNaSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MeldNaSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("meld_na_serial_delta_panel_scored", score=score, band=band)
        return [finding]
