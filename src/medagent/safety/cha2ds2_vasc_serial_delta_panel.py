"""Cha2ds2VascSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / CHA2DS2-VASc serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `Cha2ds2VascStrokeRiskScorer` / `HeartSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Cha2ds2VascSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Cha2ds2VascSerialDeltaFactors:
    """Simplified Cha2ds2VascSerialDeltaPanel factors."""

    prior_vasc_elevated: int = 0
    new_chf: int = 0
    new_hypertension: int = 0
    age_band_up: int = 0
    new_diabetes: int = 0
    prior_stroke_tia: int = 0
    vascular_disease_new: int = 0


class Cha2ds2VascSerialDeltaPanel:
    """Compute advisory Cha2ds2VascSerialDeltaRisk findings."""

    def check(self, factors: Cha2ds2VascSerialDeltaFactors) -> list[Cha2ds2VascSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_vasc_elevated": factors.prior_vasc_elevated,
            "new_chf": factors.new_chf,
            "new_hypertension": factors.new_hypertension,
            "age_band_up": factors.age_band_up,
            "new_diabetes": factors.new_diabetes,
            "prior_stroke_tia": factors.prior_stroke_tia,
            "vascular_disease_new": factors.vascular_disease_new,
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
            "RESEARCH USE ONLY: Cha2ds2VascSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Cha2ds2VascSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("cha2ds2_vasc_serial_delta_panel_scored", score=score, band=band)
        return [finding]
