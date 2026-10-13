"""MallampatiAirwayScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ASA Mallampati airway class screen gap for
offline medical-ward agent pipelines.
Distinct from `StopBangOsaScorer` / `GcsNeurologicStatusScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import MallampatiAirwayRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MallampatiAirwayFactors:
    """Simplified MallampatiAirwayScorer factors."""

    class_i_ok: int = 0
    class_ii_ok: int = 0
    class_iii_ok: int = 0
    class_iv_ok: int = 0


class MallampatiAirwayScorer:
    """Compute advisory MallampatiAirwayRisk findings."""

    def check(self, factors: MallampatiAirwayFactors) -> list[MallampatiAirwayRisk]:
        """Return one advisory finding."""

        binaries = {
            "class_i_ok": factors.class_i_ok,
            "class_ii_ok": factors.class_ii_ok,
            "class_iii_ok": factors.class_iii_ok,
            "class_iv_ok": factors.class_iv_ok,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 2:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: MallampatiAirwayScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = MallampatiAirwayRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("mallampati_airway_scorer_scored", score=score, band=band)
        return [finding]
