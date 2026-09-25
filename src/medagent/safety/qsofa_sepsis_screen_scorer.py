"""QSofaSepsisScreenScorer (research-only clinical score).

Advisory scorer closing the MDCalc / SCCM / EHR qSOFA sepsis screen gap for
offline agent pipelines.
Distinct from ``SofaOrganFailureScorer / VitalsTriageChecker``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import QSofaSepsisScreenRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class QSofaSepsisScreenFactors:
    """qSOFA binary factors (0/1 each)."""

    respiratory_rate_ge_22: int = 0
    altered_mentation: int = 0
    systolic_bp_le_100: int = 0


class QSofaSepsisScreenScorer:
    """Compute advisory QSofaSepsisScreenRisk findings."""

    def check(self, factors: QSofaSepsisScreenFactors) -> list[QSofaSepsisScreenRisk]:
        """Return one advisory finding."""

        domains = {
            "respiratory_rate_ge_22": factors.respiratory_rate_ge_22,
            "altered_mentation": factors.altered_mentation,
            "systolic_bp_le_100": factors.systolic_bp_le_100,
        }
        for name, points in domains.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        score = sum(domains.values())
        positive = [k for k, v in domains.items() if v > 0]
        if score >= 2:
            band = "high"
            severity = Severity.HIGH
        elif score == 1:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: QSofaSepsisScreenScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = QSofaSepsisScreenRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("qsofa_sepsis_screen_scorer_scored", score=score, band=band)
        return [finding]
