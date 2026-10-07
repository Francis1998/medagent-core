"""OttawaSahRuleScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACEP Ottawa SAH Rule gap for
offline medical-ward agent pipelines.
Distinct from ``HuntHessSahScorer / WfnsSahScorer / FisherGradeScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import OttawaSahRuleRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OttawaSahRuleFactors:
    """Simplified OttawaSahRuleScorer factors."""

    age_ge_40: int = 0
    neck_pain_stiffness: int = 0
    witnessed_loss_consciousness: int = 0
    onset_during_exertion: int = 0
    thunderclap_headline: int = 0
    limited_neck_flexion: int = 0


class OttawaSahRuleScorer:
    """Compute advisory OttawaSahRuleRisk findings."""

    def check(self, factors: OttawaSahRuleFactors) -> list[OttawaSahRuleRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_40": factors.age_ge_40,
            "neck_pain_stiffness": factors.neck_pain_stiffness,
            "witnessed_loss_consciousness": factors.witnessed_loss_consciousness,
            "onset_during_exertion": factors.onset_during_exertion,
            "thunderclap_headline": factors.thunderclap_headline,
            "limited_neck_flexion": factors.limited_neck_flexion,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 3:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: OttawaSahRuleScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = OttawaSahRuleRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ottawa_sah_rule_scorer_scored", score=score, band=band)
        return [finding]
