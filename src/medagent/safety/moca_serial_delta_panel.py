"""MocaSerialDeltaPanel.

Advisory scorer closing the MDCalc / MoCA cognition serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `FourScoreSerialDeltaPanel` / `GcsSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MocaSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MocaSerialDeltaFactors:
    """Simplified MocaSerialDeltaPanel factors."""

    visuospatial_decline: int = 0
    naming_decline: int = 0
    attention_decline: int = 0
    language_decline: int = 0
    abstraction_decline: int = 0
    delayed_recall_decline: int = 0


class MocaSerialDeltaPanel:
    """Compute advisory MocaSerialDeltaRisk findings."""

    def check(self, factors: MocaSerialDeltaFactors) -> list[MocaSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "visuospatial_decline": factors.visuospatial_decline,
            "naming_decline": factors.naming_decline,
            "attention_decline": factors.attention_decline,
            "language_decline": factors.language_decline,
            "abstraction_decline": factors.abstraction_decline,
            "delayed_recall_decline": factors.delayed_recall_decline,
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
            "RESEARCH USE ONLY: MocaSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MocaSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("moca_serial_delta_panel_scored", score=score, band=band)
        return [finding]
