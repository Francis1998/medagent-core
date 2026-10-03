"""RockallGiBleedScorer (research-only clinical score).

Advisory scorer closing the MDCalc / BSG / EHR Rockall upper-GI bleed score gap for
offline medical-ward agent pipelines.
Distinct from ``GlasgowBlatchfordScorer / Curb65PneumoniaScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RockallGiBleedRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RockallGiBleedFactors:
    """Simplified RockallGiBleedScorer factors."""

    age_ge_60: int = 0
    age_ge_80: int = 0
    pulse_ge_100: int = 0
    sbp_lt_100: int = 0
    comorbidity: int = 0
    major_stigmata: int = 0


class RockallGiBleedScorer:
    """Compute advisory RockallGiBleedRisk findings."""

    def check(self, factors: RockallGiBleedFactors) -> list[RockallGiBleedRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_60": factors.age_ge_60,
            "age_ge_80": factors.age_ge_80,
            "pulse_ge_100": factors.pulse_ge_100,
            "sbp_lt_100": factors.sbp_lt_100,
            "comorbidity": factors.comorbidity,
            "major_stigmata": factors.major_stigmata,
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
            "RESEARCH USE ONLY: RockallGiBleedScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RockallGiBleedRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("rockall_gi_bleed_scorer_scored", score=score, band=band)
        return [finding]
