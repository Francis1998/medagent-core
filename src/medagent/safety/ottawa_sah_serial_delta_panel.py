"""OttawaSahSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Ottawa SAH Rule serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `OttawaSahRuleScorer` / `HuntHessSahScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import OttawaSahSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OttawaSahSerialDeltaFactors:
    """Simplified OttawaSahSerialDeltaPanel factors."""

    prior_ottawa_sah_positive: int = 0
    new_thunderclap: int = 0
    neck_stiffness_new: int = 0
    loc_witnessed_new: int = 0
    exertion_onset_new: int = 0
    limited_flexion_new: int = 0


class OttawaSahSerialDeltaPanel:
    """Compute advisory OttawaSahSerialDeltaRisk findings."""

    def check(self, factors: OttawaSahSerialDeltaFactors) -> list[OttawaSahSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_ottawa_sah_positive": factors.prior_ottawa_sah_positive,
            "new_thunderclap": factors.new_thunderclap,
            "neck_stiffness_new": factors.neck_stiffness_new,
            "loc_witnessed_new": factors.loc_witnessed_new,
            "exertion_onset_new": factors.exertion_onset_new,
            "limited_flexion_new": factors.limited_flexion_new,
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
            "RESEARCH USE ONLY: OttawaSahSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = OttawaSahSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ottawa_sah_serial_delta_panel_scored", score=score, band=band)
        return [finding]
