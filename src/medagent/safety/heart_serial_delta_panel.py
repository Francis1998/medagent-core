"""HeartSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / HEART serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `HeartScoreAcsScorer` / `MewsSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import HeartSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HeartSerialDeltaFactors:
    """Simplified HeartSerialDeltaPanel factors."""

    prior_heart_elevated: int = 0
    current_heart_rise: int = 0
    troponin_worsening: int = 0
    ecg_worsening: int = 0
    history_worsening: int = 0
    risk_factor_worsening: int = 0


class HeartSerialDeltaPanel:
    """Compute advisory HeartSerialDeltaRisk findings."""

    def check(self, factors: HeartSerialDeltaFactors) -> list[HeartSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_heart_elevated": factors.prior_heart_elevated,
            "current_heart_rise": factors.current_heart_rise,
            "troponin_worsening": factors.troponin_worsening,
            "ecg_worsening": factors.ecg_worsening,
            "history_worsening": factors.history_worsening,
            "risk_factor_worsening": factors.risk_factor_worsening,
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
            "RESEARCH USE ONLY: HeartSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = HeartSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("heart_serial_delta_panel_scored", score=score, band=band)
        return [finding]
