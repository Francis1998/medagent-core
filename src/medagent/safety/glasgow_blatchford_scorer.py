"""GlasgowBlatchfordScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACG / EHR Glasgow-Blatchford GI bleed score gap for
offline medical-ward agent pipelines.
Distinct from ``RockallGiBleedScorer / Curb65PneumoniaScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import GlasgowBlatchfordRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GlasgowBlatchfordFactors:
    """Simplified GlasgowBlatchfordScorer factors."""

    bun_ge_6_5: int = 0
    bun_ge_10_0: int = 0
    bun_ge_25_0: int = 0
    hb_lt_13_male_or_12_female: int = 0
    hb_lt_10: int = 0
    sbp_90_109: int = 0
    sbp_lt_90: int = 0
    hr_ge_100: int = 0
    melena: int = 0
    syncope: int = 0
    liver_disease: int = 0
    heart_failure: int = 0


class GlasgowBlatchfordScorer:
    """Compute advisory GlasgowBlatchfordRisk findings."""

    def check(self, factors: GlasgowBlatchfordFactors) -> list[GlasgowBlatchfordRisk]:
        """Return one advisory finding."""

        binaries = {
            "bun_ge_6_5": factors.bun_ge_6_5,
            "bun_ge_10_0": factors.bun_ge_10_0,
            "bun_ge_25_0": factors.bun_ge_25_0,
            "hb_lt_13_male_or_12_female": factors.hb_lt_13_male_or_12_female,
            "hb_lt_10": factors.hb_lt_10,
            "sbp_90_109": factors.sbp_90_109,
            "sbp_lt_90": factors.sbp_lt_90,
            "hr_ge_100": factors.hr_ge_100,
            "melena": factors.melena,
            "syncope": factors.syncope,
            "liver_disease": factors.liver_disease,
            "heart_failure": factors.heart_failure,
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
            "RESEARCH USE ONLY: GlasgowBlatchfordScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = GlasgowBlatchfordRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("glasgow_blatchford_scorer_scored", score=score, band=band)
        return [finding]
