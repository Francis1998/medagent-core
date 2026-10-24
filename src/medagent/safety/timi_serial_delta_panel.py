"""TimiSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / TIMI serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `TimiUaNstemiScorer` / `HeartSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, TimiSerialDeltaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TimiSerialDeltaFactors:
    """Simplified TimiSerialDeltaPanel factors."""

    prior_timi_elevated: int = 0
    current_timi_rise: int = 0
    troponin_rise: int = 0
    st_deviation_worsening: int = 0
    angina_frequency_rise: int = 0
    asa_use_recent: int = 0


class TimiSerialDeltaPanel:
    """Compute advisory TimiSerialDeltaRisk findings."""

    def check(self, factors: TimiSerialDeltaFactors) -> list[TimiSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_timi_elevated": factors.prior_timi_elevated,
            "current_timi_rise": factors.current_timi_rise,
            "troponin_rise": factors.troponin_rise,
            "st_deviation_worsening": factors.st_deviation_worsening,
            "angina_frequency_rise": factors.angina_frequency_rise,
            "asa_use_recent": factors.asa_use_recent,
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
            "RESEARCH USE ONLY: TimiSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = TimiSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("timi_serial_delta_panel_scored", score=score, band=band)
        return [finding]
