"""BarthelSerialDeltaPanel.

Advisory scorer closing the MDCalc / Barthel ADL serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `BarthelAdlScorer` / `KarnofskySerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import BarthelSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BarthelSerialDeltaFactors:
    """Simplified BarthelSerialDeltaPanel factors."""

    feeding_decline: int = 0
    bathing_decline: int = 0
    dressing_decline: int = 0
    toileting_decline: int = 0
    mobility_decline: int = 0
    continence_worsening: int = 0


class BarthelSerialDeltaPanel:
    """Compute advisory BarthelSerialDeltaRisk findings."""

    def check(self, factors: BarthelSerialDeltaFactors) -> list[BarthelSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "feeding_decline": factors.feeding_decline,
            "bathing_decline": factors.bathing_decline,
            "dressing_decline": factors.dressing_decline,
            "toileting_decline": factors.toileting_decline,
            "mobility_decline": factors.mobility_decline,
            "continence_worsening": factors.continence_worsening,
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
            "RESEARCH USE ONLY: BarthelSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = BarthelSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("barthel_serial_delta_panel_scored", score=score, band=band)
        return [finding]
