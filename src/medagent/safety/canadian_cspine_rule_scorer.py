"""CanadianCspineRuleScorer (research-only clinical score).

Advisory scorer closing the MDCalc / CAEP / EHR Canadian C-spine rule gap for
offline medical-ward agent pipelines.
Distinct from ``OttawaAnkleRuleScorer / FallRiskChecker``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CanadianCspineRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CanadianCspineFactors:
    """Simplified CanadianCspineRuleScorer factors."""

    age_ge_65: int = 0
    dangerous_mechanism: int = 0
    paresthesias: int = 0
    midline_tenderness: int = 0
    unable_rotate_45: int = 0


class CanadianCspineRuleScorer:
    """Compute advisory CanadianCspineRisk findings."""

    def check(self, factors: CanadianCspineFactors) -> list[CanadianCspineRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_65": factors.age_ge_65,
            "dangerous_mechanism": factors.dangerous_mechanism,
            "paresthesias": factors.paresthesias,
            "midline_tenderness": factors.midline_tenderness,
            "unable_rotate_45": factors.unable_rotate_45,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score == 0:
            band = "imaging_not_indicated"
            severity = Severity.LOW
        elif score == 1:
            band = "consider_imaging"
            severity = Severity.MODERATE
        else:
            band = "imaging_indicated"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: CanadianCspineRuleScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CanadianCspineRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("canadian_cspine_rule_scorer_scored", score=score, band=band)
        return [finding]
