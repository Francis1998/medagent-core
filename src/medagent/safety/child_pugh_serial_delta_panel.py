"""ChildPughSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Child-Pugh serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `ChildPughLiverSeverityScorer` / `MeldNaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ChildPughSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ChildPughSerialDeltaFactors:
    """Simplified ChildPughSerialDeltaPanel factors."""

    prior_child_pugh_elevated: int = 0
    bilirubin_up: int = 0
    albumin_down: int = 0
    inr_up: int = 0
    ascites_new: int = 0
    encephalopathy_new: int = 0


class ChildPughSerialDeltaPanel:
    """Compute advisory ChildPughSerialDeltaRisk findings."""

    def check(self, factors: ChildPughSerialDeltaFactors) -> list[ChildPughSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_child_pugh_elevated": factors.prior_child_pugh_elevated,
            "bilirubin_up": factors.bilirubin_up,
            "albumin_down": factors.albumin_down,
            "inr_up": factors.inr_up,
            "ascites_new": factors.ascites_new,
            "encephalopathy_new": factors.encephalopathy_new,
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
            "RESEARCH USE ONLY: ChildPughSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ChildPughSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("child_pugh_serial_delta_panel_scored", score=score, band=band)
        return [finding]
