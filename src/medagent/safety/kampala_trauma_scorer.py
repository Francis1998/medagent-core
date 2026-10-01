"""KampalaTraumaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / WHO / EHR Kampala Trauma Score score gap for
offline medical-ward agent pipelines.
Distinct from ``LrinecNecfascScorer / SofaOrganFailureScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import KampalaTraumaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KampalaTraumaFactors:
    """Simplified KampalaTraumaScorer factors."""

    age_extreme: int = 0
    sbp_lt_90: int = 0
    respiratory_distress: int = 0
    neuro_deficit: int = 0
    serious_injury: int = 0
    no_pulse_ox: int = 0


class KampalaTraumaScorer:
    """Compute advisory KampalaTraumaRisk findings."""

    def check(self, factors: KampalaTraumaFactors) -> list[KampalaTraumaRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_extreme": factors.age_extreme,
            "sbp_lt_90": factors.sbp_lt_90,
            "respiratory_distress": factors.respiratory_distress,
            "neuro_deficit": factors.neuro_deficit,
            "serious_injury": factors.serious_injury,
            "no_pulse_ox": factors.no_pulse_ox,
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
            "RESEARCH USE ONLY: KampalaTraumaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = KampalaTraumaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("kampala_trauma_scorer_scored", score=score, band=band)
        return [finding]
