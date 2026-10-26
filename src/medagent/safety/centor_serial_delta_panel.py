"""CentorSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Centor serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `CentorStrepPharyngitisScorer` / `HeartSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CentorSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CentorSerialDeltaFactors:
    """Simplified CentorSerialDeltaPanel factors."""

    prior_centor_elevated: int = 0
    new_fever: int = 0
    new_tender_nodes: int = 0
    tonsil_exudate_new: int = 0
    cough_absent_new: int = 0
    age_band_up: int = 0


class CentorSerialDeltaPanel:
    """Compute advisory CentorSerialDeltaRisk findings."""

    def check(self, factors: CentorSerialDeltaFactors) -> list[CentorSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_centor_elevated": factors.prior_centor_elevated,
            "new_fever": factors.new_fever,
            "new_tender_nodes": factors.new_tender_nodes,
            "tonsil_exudate_new": factors.tonsil_exudate_new,
            "cough_absent_new": factors.cough_absent_new,
            "age_band_up": factors.age_band_up,
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
            "RESEARCH USE ONLY: CentorSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CentorSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("centor_serial_delta_panel_scored", score=score, band=band)
        return [finding]
