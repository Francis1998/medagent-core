"""SanFranciscoSyncopeRuleScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACEP / EHR San Francisco Syncope Rule gap for
offline medical-ward agent pipelines.
Distinct from ``NihssStrokeScorer / FallRiskChecker``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import SanFranciscoSyncopeRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SanFranciscoSyncopeFactors:
    """Simplified SanFranciscoSyncopeRuleScorer factors."""

    chf_history: int = 0
    hematocrit_lt_30: int = 0
    ecg_abnormal: int = 0
    shortness_of_breath: int = 0
    systolic_bp_lt_90: int = 0


class SanFranciscoSyncopeRuleScorer:
    """Compute advisory SanFranciscoSyncopeRisk findings."""

    def check(self, factors: SanFranciscoSyncopeFactors) -> list[SanFranciscoSyncopeRisk]:
        """Return one advisory finding."""

        binaries = {
            "chf_history": factors.chf_history,
            "hematocrit_lt_30": factors.hematocrit_lt_30,
            "ecg_abnormal": factors.ecg_abnormal,
            "shortness_of_breath": factors.shortness_of_breath,
            "systolic_bp_lt_90": factors.systolic_bp_lt_90,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score == 0:
            band = "low_risk"
            severity = Severity.LOW
        elif score == 1:
            band = "moderate_risk"
            severity = Severity.MODERATE
        else:
            band = "high_risk"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: SanFranciscoSyncopeRuleScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = SanFranciscoSyncopeRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("san_francisco_syncope_rule_scorer_scored", score=score, band=band)
        return [finding]
