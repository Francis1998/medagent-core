"""Phq9SerialDeltaPanel.

Advisory scorer closing the MDCalc / PHQ-9 depression serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `Phq9DepressionScorer` / `Gad7AnxietyScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Phq9SerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Phq9SerialDeltaFactors:
    """Simplified Phq9SerialDeltaPanel factors."""

    anhedonia_worsening: int = 0
    mood_worsening: int = 0
    sleep_worsening: int = 0
    energy_worsening: int = 0
    appetite_worsening: int = 0
    self_worth_worsening: int = 0


class Phq9SerialDeltaPanel:
    """Compute advisory Phq9SerialDeltaRisk findings."""

    def check(self, factors: Phq9SerialDeltaFactors) -> list[Phq9SerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "anhedonia_worsening": factors.anhedonia_worsening,
            "mood_worsening": factors.mood_worsening,
            "sleep_worsening": factors.sleep_worsening,
            "energy_worsening": factors.energy_worsening,
            "appetite_worsening": factors.appetite_worsening,
            "self_worth_worsening": factors.self_worth_worsening,
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
            "RESEARCH USE ONLY: Phq9SerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Phq9SerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("phq9_serial_delta_panel_scored", score=score, band=band)
        return [finding]
