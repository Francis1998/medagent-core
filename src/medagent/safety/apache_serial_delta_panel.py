"""ApacheSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / APACHE serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `ApacheIiLiteScorer` / `SofaSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ApacheSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ApacheSerialDeltaFactors:
    """Simplified ApacheSerialDeltaPanel factors."""

    prior_apache_elevated: int = 0
    current_apache_rise: int = 0
    resp_worsening: int = 0
    cardio_worsening: int = 0
    neuro_worsening: int = 0
    renal_worsening: int = 0


class ApacheSerialDeltaPanel:
    """Compute advisory ApacheSerialDeltaRisk findings."""

    def check(self, factors: ApacheSerialDeltaFactors) -> list[ApacheSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_apache_elevated": factors.prior_apache_elevated,
            "current_apache_rise": factors.current_apache_rise,
            "resp_worsening": factors.resp_worsening,
            "cardio_worsening": factors.cardio_worsening,
            "neuro_worsening": factors.neuro_worsening,
            "renal_worsening": factors.renal_worsening,
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
            "RESEARCH USE ONLY: ApacheSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ApacheSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("apache_serial_delta_panel_scored", score=score, band=band)
        return [finding]
