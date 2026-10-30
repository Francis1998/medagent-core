"""CanadianCtHeadSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Canadian CT Head Rule serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `CanadianCtHeadScorer` / `PecarnSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CanadianCtHeadSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CanadianCtHeadSerialDeltaFactors:
    """Simplified CanadianCtHeadSerialDeltaPanel factors."""

    prior_rule_positive: int = 0
    gcs_drop: int = 0
    vomiting_new: int = 0
    amnesia_worsened: int = 0
    dangerous_mechanism_new: int = 0
    anticoag_started: int = 0


class CanadianCtHeadSerialDeltaPanel:
    """Compute advisory CanadianCtHeadSerialDeltaRisk findings."""

    def check(
        self, factors: CanadianCtHeadSerialDeltaFactors
    ) -> list[CanadianCtHeadSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_rule_positive": factors.prior_rule_positive,
            "gcs_drop": factors.gcs_drop,
            "vomiting_new": factors.vomiting_new,
            "amnesia_worsened": factors.amnesia_worsened,
            "dangerous_mechanism_new": factors.dangerous_mechanism_new,
            "anticoag_started": factors.anticoag_started,
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
            "RESEARCH USE ONLY: CanadianCtHeadSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CanadianCtHeadSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("canadian_ct_head_serial_delta_panel_scored", score=score, band=band)
        return [finding]
