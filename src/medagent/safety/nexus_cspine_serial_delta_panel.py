"""NexusCspineSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / NEXUS C-spine serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `NexusCspineScorer` / `CanadianCspineRuleScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import NexusCspineSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NexusCspineSerialDeltaFactors:
    """Simplified NexusCspineSerialDeltaPanel factors."""

    prior_nexus_positive: int = 0
    midline_tenderness_new: int = 0
    focal_neuro_new: int = 0
    altered_alertness_new: int = 0
    intoxication_new: int = 0
    distracting_injury_new: int = 0


class NexusCspineSerialDeltaPanel:
    """Compute advisory NexusCspineSerialDeltaRisk findings."""

    def check(self, factors: NexusCspineSerialDeltaFactors) -> list[NexusCspineSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_nexus_positive": factors.prior_nexus_positive,
            "midline_tenderness_new": factors.midline_tenderness_new,
            "focal_neuro_new": factors.focal_neuro_new,
            "altered_alertness_new": factors.altered_alertness_new,
            "intoxication_new": factors.intoxication_new,
            "distracting_injury_new": factors.distracting_injury_new,
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
            "RESEARCH USE ONLY: NexusCspineSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = NexusCspineSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("nexus_cspine_serial_delta_panel_scored", score=score, band=band)
        return [finding]
