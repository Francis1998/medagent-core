"""ForresterSerialDeltaPanel.

Advisory scorer closing the MDCalc / Forrester hemodynamic serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `ForresterClassScorer` / `KillipSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ForresterSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ForresterSerialDeltaFactors:
    """Simplified ForresterSerialDeltaPanel factors."""

    prior_forrester_elevated: int = 0
    pulmonary_congestion_worsen: int = 0
    hypoperfusion_new: int = 0
    filling_pressure_rise: int = 0
    cardiac_index_drop: int = 0
    vasopressor_escalation: int = 0


class ForresterSerialDeltaPanel:
    """Compute advisory ForresterSerialDeltaRisk findings."""

    def check(self, factors: ForresterSerialDeltaFactors) -> list[ForresterSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_forrester_elevated": factors.prior_forrester_elevated,
            "pulmonary_congestion_worsen": factors.pulmonary_congestion_worsen,
            "hypoperfusion_new": factors.hypoperfusion_new,
            "filling_pressure_rise": factors.filling_pressure_rise,
            "cardiac_index_drop": factors.cardiac_index_drop,
            "vasopressor_escalation": factors.vasopressor_escalation,
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
            "RESEARCH USE ONLY: ForresterSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ForresterSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("forrester_serial_delta_panel_scored", score=score, band=band)
        return [finding]
