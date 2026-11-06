"""KatzSerialDeltaPanel.

Advisory scorer closing the MDCalc / Katz ADL serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `BarthelSerialDeltaPanel` / `KarnofskySerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import KatzSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KatzSerialDeltaFactors:
    """Simplified KatzSerialDeltaPanel factors."""

    bathing_decline: int = 0
    dressing_decline: int = 0
    toileting_decline: int = 0
    transferring_decline: int = 0
    continence_decline: int = 0
    feeding_decline: int = 0


class KatzSerialDeltaPanel:
    """Compute advisory KatzSerialDeltaRisk findings."""

    def check(self, factors: KatzSerialDeltaFactors) -> list[KatzSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "bathing_decline": factors.bathing_decline,
            "dressing_decline": factors.dressing_decline,
            "toileting_decline": factors.toileting_decline,
            "transferring_decline": factors.transferring_decline,
            "continence_decline": factors.continence_decline,
            "feeding_decline": factors.feeding_decline,
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
            "RESEARCH USE ONLY: KatzSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = KatzSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("katz_serial_delta_panel_scored", score=score, band=band)
        return [finding]
