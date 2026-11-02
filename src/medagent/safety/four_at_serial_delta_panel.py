"""FourAtSerialDeltaPanel.

Advisory scorer closing the MDCalc / 4AT delirium serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `FourAtDeliriumScorer` / `FourScoreSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import FourAtSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FourAtSerialDeltaFactors:
    """Simplified FourAtSerialDeltaPanel factors."""

    prior_four_at_elevated: int = 0
    alertness_drop: int = 0
    amt4_worsen: int = 0
    attention_fail_new: int = 0
    acute_change_flag: int = 0
    fluctuation_new: int = 0


class FourAtSerialDeltaPanel:
    """Compute advisory FourAtSerialDeltaRisk findings."""

    def check(self, factors: FourAtSerialDeltaFactors) -> list[FourAtSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_four_at_elevated": factors.prior_four_at_elevated,
            "alertness_drop": factors.alertness_drop,
            "amt4_worsen": factors.amt4_worsen,
            "attention_fail_new": factors.attention_fail_new,
            "acute_change_flag": factors.acute_change_flag,
            "fluctuation_new": factors.fluctuation_new,
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
            "RESEARCH USE ONLY: FourAtSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = FourAtSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("four_at_serial_delta_panel_scored", score=score, band=band)
        return [finding]
