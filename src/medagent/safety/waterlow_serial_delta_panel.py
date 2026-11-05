"""WaterlowSerialDeltaPanel.

Advisory scorer closing the MDCalc / Waterlow pressure-ulcer serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `BradenSerialDeltaPanel` / `BradenPressureScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WaterlowSerialDeltaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WaterlowSerialDeltaFactors:
    """Simplified WaterlowSerialDeltaPanel factors."""

    build_weight_worsening: int = 0
    continence_worsening: int = 0
    skin_type_worsening: int = 0
    mobility_decline: int = 0
    sex_age_risk_rise: int = 0
    appetite_decline: int = 0


class WaterlowSerialDeltaPanel:
    """Compute advisory WaterlowSerialDeltaRisk findings."""

    def check(self, factors: WaterlowSerialDeltaFactors) -> list[WaterlowSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "build_weight_worsening": factors.build_weight_worsening,
            "continence_worsening": factors.continence_worsening,
            "skin_type_worsening": factors.skin_type_worsening,
            "mobility_decline": factors.mobility_decline,
            "sex_age_risk_rise": factors.sex_age_risk_rise,
            "appetite_decline": factors.appetite_decline,
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
            "RESEARCH USE ONLY: WaterlowSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WaterlowSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("waterlow_serial_delta_panel_scored", score=score, band=band)
        return [finding]
