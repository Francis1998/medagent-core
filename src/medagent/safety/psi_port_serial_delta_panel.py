"""PsiPortSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / PSI/PORT serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `PsiPortPneumoniaScorer` / `Curb65SerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PsiPortSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PsiPortSerialDeltaFactors:
    """Simplified PsiPortSerialDeltaPanel factors."""

    prior_psi_elevated: int = 0
    age_band_worsened: int = 0
    comorbidity_new: int = 0
    vitals_worsened: int = 0
    labs_worsened: int = 0
    oxygen_need_new: int = 0


class PsiPortSerialDeltaPanel:
    """Compute advisory PsiPortSerialDeltaRisk findings."""

    def check(self, factors: PsiPortSerialDeltaFactors) -> list[PsiPortSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_psi_elevated": factors.prior_psi_elevated,
            "age_band_worsened": factors.age_band_worsened,
            "comorbidity_new": factors.comorbidity_new,
            "vitals_worsened": factors.vitals_worsened,
            "labs_worsened": factors.labs_worsened,
            "oxygen_need_new": factors.oxygen_need_new,
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
            "RESEARCH USE ONLY: PsiPortSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PsiPortSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("psi_port_serial_delta_panel_scored", score=score, band=band)
        return [finding]
