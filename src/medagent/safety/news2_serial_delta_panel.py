"""News2SerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / NEWS2 serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `News2EarlyWarningScorer` / `SofaOrganFailureScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import News2SerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class News2SerialDeltaFactors:
    """Simplified News2SerialDeltaPanel factors."""

    prior_news2_elevated: int = 0
    current_news2_rise: int = 0
    multi_parameter_rise: int = 0
    oxygen_escalation: int = 0
    consciousness_worsening: int = 0
    ward_escalation_flag: int = 0


class News2SerialDeltaPanel:
    """Compute advisory News2SerialDeltaRisk findings."""

    def check(self, factors: News2SerialDeltaFactors) -> list[News2SerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_news2_elevated": factors.prior_news2_elevated,
            "current_news2_rise": factors.current_news2_rise,
            "multi_parameter_rise": factors.multi_parameter_rise,
            "oxygen_escalation": factors.oxygen_escalation,
            "consciousness_worsening": factors.consciousness_worsening,
            "ward_escalation_flag": factors.ward_escalation_flag,
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
            "RESEARCH USE ONLY: News2SerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = News2SerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("news2_serial_delta_panel_scored", score=score, band=band)
        return [finding]
