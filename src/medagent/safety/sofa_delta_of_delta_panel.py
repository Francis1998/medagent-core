"""SofaDeltaOfDeltaPanel.

Advisory scorer closing the MDCalc / SOFA Δ-of-Δ residual organ-failure panel gap for
offline medical-ward agent pipelines.
Distinct from `SofaSerialDeltaPanel` / `SofaOrganFailureScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, SofaDeltaOfDeltaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SofaDeltaOfDeltaFactors:
    """Simplified SofaDeltaOfDeltaPanel factors."""

    respiration_accel: int = 0
    coagulation_accel: int = 0
    liver_accel: int = 0
    cardiovascular_accel: int = 0
    cns_accel: int = 0
    renal_accel: int = 0


class SofaDeltaOfDeltaPanel:
    """Compute advisory SofaDeltaOfDeltaRisk findings."""

    def check(self, factors: SofaDeltaOfDeltaFactors) -> list[SofaDeltaOfDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "respiration_accel": factors.respiration_accel,
            "coagulation_accel": factors.coagulation_accel,
            "liver_accel": factors.liver_accel,
            "cardiovascular_accel": factors.cardiovascular_accel,
            "cns_accel": factors.cns_accel,
            "renal_accel": factors.renal_accel,
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
            "RESEARCH USE ONLY: SofaDeltaOfDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = SofaDeltaOfDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("sofa_delta_of_delta_panel_scored", score=score, band=band)
        return [finding]
