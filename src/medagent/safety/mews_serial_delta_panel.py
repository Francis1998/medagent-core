"""MewsSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / MEWS serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `MewsScorer` / `News2SerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MewsSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MewsSerialDeltaFactors:
    """Simplified MewsSerialDeltaPanel factors."""

    prior_mews_elevated: int = 0
    current_mews_rise: int = 0
    resp_worsening: int = 0
    hr_worsening: int = 0
    bp_worsening: int = 0
    avs_worsening: int = 0


class MewsSerialDeltaPanel:
    """Compute advisory MewsSerialDeltaRisk findings."""

    def check(self, factors: MewsSerialDeltaFactors) -> list[MewsSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_mews_elevated": factors.prior_mews_elevated,
            "current_mews_rise": factors.current_mews_rise,
            "resp_worsening": factors.resp_worsening,
            "hr_worsening": factors.hr_worsening,
            "bp_worsening": factors.bp_worsening,
            "avs_worsening": factors.avs_worsening,
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
            "RESEARCH USE ONLY: MewsSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MewsSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("mews_serial_delta_panel_scored", score=score, band=band)
        return [finding]
