"""Gad7SerialDeltaPanel.

Advisory scorer closing the MDCalc / GAD-7 anxiety serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `Gad7AnxietyScorer` / `Phq9DepressionScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Gad7SerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Gad7SerialDeltaFactors:
    """Simplified Gad7SerialDeltaPanel factors."""

    nervous_worsening: int = 0
    control_worry_worsening: int = 0
    worry_breadth_worsening: int = 0
    relax_difficulty_worsening: int = 0
    restless_worsening: int = 0
    irritable_worsening: int = 0


class Gad7SerialDeltaPanel:
    """Compute advisory Gad7SerialDeltaRisk findings."""

    def check(self, factors: Gad7SerialDeltaFactors) -> list[Gad7SerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "nervous_worsening": factors.nervous_worsening,
            "control_worry_worsening": factors.control_worry_worsening,
            "worry_breadth_worsening": factors.worry_breadth_worsening,
            "relax_difficulty_worsening": factors.relax_difficulty_worsening,
            "restless_worsening": factors.restless_worsening,
            "irritable_worsening": factors.irritable_worsening,
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
            "RESEARCH USE ONLY: Gad7SerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Gad7SerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("gad7_serial_delta_panel_scored", score=score, band=band)
        return [finding]
