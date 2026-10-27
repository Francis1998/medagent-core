"""AlvaradoSerialDeltaPanel (research-only clinical score).

Advisory scorer closing the MDCalc / Alvarado serial delta-trend panel gap for
offline medical-ward agent pipelines.
Distinct from `AlvaradoAppendicitisScorer` / `CentorSerialDeltaPanel`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import AlvaradoSerialDeltaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AlvaradoSerialDeltaFactors:
    """Simplified AlvaradoSerialDeltaPanel factors."""

    prior_alvarado_elevated: int = 0
    migration_pain_new: int = 0
    anorexia_new: int = 0
    nausea_vomit_new: int = 0
    rlq_tenderness_up: int = 0
    leukocytosis_up: int = 0


class AlvaradoSerialDeltaPanel:
    """Compute advisory AlvaradoSerialDeltaRisk findings."""

    def check(self, factors: AlvaradoSerialDeltaFactors) -> list[AlvaradoSerialDeltaRisk]:
        """Return one advisory finding."""

        binaries = {
            "prior_alvarado_elevated": factors.prior_alvarado_elevated,
            "migration_pain_new": factors.migration_pain_new,
            "anorexia_new": factors.anorexia_new,
            "nausea_vomit_new": factors.nausea_vomit_new,
            "rlq_tenderness_up": factors.rlq_tenderness_up,
            "leukocytosis_up": factors.leukocytosis_up,
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
            "RESEARCH USE ONLY: AlvaradoSerialDeltaPanel total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = AlvaradoSerialDeltaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("alvarado_serial_delta_panel_scored", score=score, band=band)
        return [finding]
