"""QsofaSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / qSOFA serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `QSofaSepsisScreenScorer` / `News2SerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import QsofaSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class QsofaSerialDeltaFactors:
    """Simplified QsofaSerialDeltaPanel factors."""

    prior_qsofa_elevated: int = 0
    current_qsofa_rise: int = 0
    rr_worsening: int = 0
    sbp_drop: int = 0
    ams_new: int = 0
    ward_escalation_flag: int = 0


class QsofaSerialDeltaPanel:
    """Compute advisory QsofaSerialDeltaRisk findings."""

    def check(self, factors: QsofaSerialDeltaFactors) -> list[QsofaSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_qsofa_elevated": factors.prior_qsofa_elevated,
            "current_qsofa_rise": factors.current_qsofa_rise,
            "rr_worsening": factors.rr_worsening,
            "sbp_drop": factors.sbp_drop,
            "ams_new": factors.ams_new,
            "ward_escalation_flag": factors.ward_escalation_flag,
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
            "RESEARCH USE ONLY: QsofaSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = QsofaSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("qsofa_serial_delta_panel_scored", score=score, band=band)
        return [finding]
