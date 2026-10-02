"""ApacheIiLiteScorer (research-only clinical score).

Advisory scorer closing the MDCalc / SCCM / EHR APACHE II lite score gap for
offline medical-ward agent pipelines.
Distinct from ``SofaOrganFailureScorer / QSofaSepsisScreenScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ApacheIiLiteRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ApacheIiLiteFactors:
    """Simplified ApacheIiLiteScorer factors."""

    temp_extreme: int = 0
    map_abnormal: int = 0
    hr_extreme: int = 0
    rr_extreme: int = 0
    oxygenation_low: int = 0
    ph_abnormal: int = 0
    sodium_abnormal: int = 0
    potassium_abnormal: int = 0
    creatinine_high: int = 0
    hct_abnormal: int = 0
    wbc_abnormal: int = 0
    gcs_low: int = 0
    chronic_health: int = 0


class ApacheIiLiteScorer:
    """Compute advisory ApacheIiLiteRisk findings."""

    def check(self, factors: ApacheIiLiteFactors) -> list[ApacheIiLiteRisk]:
        """Return one advisory finding."""

        binaries = {
            "temp_extreme": factors.temp_extreme,
            "map_abnormal": factors.map_abnormal,
            "hr_extreme": factors.hr_extreme,
            "rr_extreme": factors.rr_extreme,
            "oxygenation_low": factors.oxygenation_low,
            "ph_abnormal": factors.ph_abnormal,
            "sodium_abnormal": factors.sodium_abnormal,
            "potassium_abnormal": factors.potassium_abnormal,
            "creatinine_high": factors.creatinine_high,
            "hct_abnormal": factors.hct_abnormal,
            "wbc_abnormal": factors.wbc_abnormal,
            "gcs_low": factors.gcs_low,
            "chronic_health": factors.chronic_health,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 2:
            band = "low"
            severity = Severity.LOW
        elif score <= 4:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: ApacheIiLiteScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ApacheIiLiteRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("apache_ii_lite_scorer_scored", score=score, band=band)
        return [finding]
