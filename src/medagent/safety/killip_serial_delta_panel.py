"""KillipSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Killip serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `KillipClassScorer` / `HeartSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import KillipSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KillipSerialDeltaFactors:
    """Simplified KillipSerialDeltaPanel factors."""

    prior_killip_elevated: int = 0
    killip_class_rise: int = 0
    rales_worsening: int = 0
    s3_new: int = 0
    hypotension_onset: int = 0
    cardiogenic_shock_sign: int = 0


class KillipSerialDeltaPanel:
    """Compute advisory KillipSerialDeltaRisk findings."""

    def check(self, factors: KillipSerialDeltaFactors) -> list[KillipSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_killip_elevated": factors.prior_killip_elevated,
            "killip_class_rise": factors.killip_class_rise,
            "rales_worsening": factors.rales_worsening,
            "s3_new": factors.s3_new,
            "hypotension_onset": factors.hypotension_onset,
            "cardiogenic_shock_sign": factors.cardiogenic_shock_sign,
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
            "RESEARCH USE ONLY: KillipSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = KillipSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("killip_serial_delta_panel_scored", score=score, band=band)
        return [finding]
