"""GlasgowBlatchfordSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Glasgow-Blatchford GI bleed serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `GlasgowBlatchfordScorer` / `RockallGiBleedScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import GlasgowBlatchfordSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GlasgowBlatchfordSerialDeltaFactors:
    """Simplified GlasgowBlatchfordSerialDeltaPanel factors."""

    prior_gbs_elevated: int = 0
    bun_rise: int = 0
    hb_drop: int = 0
    sbp_drop: int = 0
    melena_new: int = 0
    syncope_new: int = 0


class GlasgowBlatchfordSerialDeltaPanel:
    """Compute advisory GlasgowBlatchfordSerialDeltaRisk findings."""

    def check(
        self, factors: GlasgowBlatchfordSerialDeltaFactors
    ) -> list[GlasgowBlatchfordSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_gbs_elevated": factors.prior_gbs_elevated,
            "bun_rise": factors.bun_rise,
            "hb_drop": factors.hb_drop,
            "sbp_drop": factors.sbp_drop,
            "melena_new": factors.melena_new,
            "syncope_new": factors.syncope_new,
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
            "RESEARCH USE ONLY: GlasgowBlatchfordSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = GlasgowBlatchfordSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("glasgow_blatchford_serial_delta_panel_scored", score=score, band=band)
        return [finding]
