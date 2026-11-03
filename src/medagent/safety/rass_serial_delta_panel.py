"""RassSerialDeltaPanel.

Advisory scorer closing the MDCalc / RASS sedation serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `RassSedationScorer` / `CamIcuDeliriumScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RassSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RassSerialDeltaFactors:
    """Simplified RassSerialDeltaPanel factors."""

    prior_rass_elevated: int = 0
    agitation_rise: int = 0
    sedation_deepening: int = 0
    ventilator_dyssynchrony: int = 0
    pain_breakthrough: int = 0
    delirium_overlap: int = 0


class RassSerialDeltaPanel:
    """Compute advisory RassSerialDeltaRisk findings."""

    def check(self, factors: RassSerialDeltaFactors) -> list[RassSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_rass_elevated": factors.prior_rass_elevated,
            "agitation_rise": factors.agitation_rise,
            "sedation_deepening": factors.sedation_deepening,
            "ventilator_dyssynchrony": factors.ventilator_dyssynchrony,
            "pain_breakthrough": factors.pain_breakthrough,
            "delirium_overlap": factors.delirium_overlap,
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
            "RESEARCH USE ONLY: RassSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RassSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("rass_serial_delta_panel_scored", score=score, band=band)
        return [finding]
