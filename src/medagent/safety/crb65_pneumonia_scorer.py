"""Crb65PneumoniaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / BTS / EHR CRB-65 pneumonia score gap for
offline medical-ward agent pipelines.
Distinct from ``Curb65PneumoniaScorer / PsiPortPneumoniaScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Crb65PneumoniaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Crb65PneumoniaFactors:
    """Simplified Crb65PneumoniaScorer factors."""

    confusion: int = 0
    respiratory_rate_ge_30: int = 0
    sbp_lt_90_or_dbp_le_60: int = 0
    age_ge_65: int = 0


class Crb65PneumoniaScorer:
    """Compute advisory Crb65PneumoniaRisk findings."""

    def check(self, factors: Crb65PneumoniaFactors) -> list[Crb65PneumoniaRisk]:
        """Return one advisory finding."""

        binaries = {
            "confusion": factors.confusion,
            "respiratory_rate_ge_30": factors.respiratory_rate_ge_30,
            "sbp_lt_90_or_dbp_le_60": factors.sbp_lt_90_or_dbp_le_60,
            "age_ge_65": factors.age_ge_65,
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
            "RESEARCH USE ONLY: Crb65PneumoniaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = Crb65PneumoniaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("crb65_pneumonia_scorer_scored", score=score, band=band)
        return [finding]
