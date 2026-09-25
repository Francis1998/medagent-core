"""News2EarlyWarningScorer (research-only clinical score).

Advisory scorer closing the MDCalc / RCP / EHR NEWS2 early-warning gap for
offline agent pipelines.
Distinct from ``VitalsTriageChecker / QSofaSepsisScreenScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified domain points (0-3 style caps) for offline unit tests — not a full
RCP chart implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import News2EarlyWarningRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class News2EarlyWarningFactors:
    """Simplified NEWS2-style domain points (each 0..3)."""

    respiration: int = 0
    oxygen_sat: int = 0
    supplemental_o2: int = 0
    temperature: int = 0
    systolic_bp: int = 0
    heart_rate: int = 0
    consciousness: int = 0


class News2EarlyWarningScorer:
    """Compute advisory News2EarlyWarningRisk findings."""

    def check(self, factors: News2EarlyWarningFactors) -> list[News2EarlyWarningRisk]:
        """Return one advisory finding."""

        domains = {
            "respiration": factors.respiration,
            "oxygen_sat": factors.oxygen_sat,
            "supplemental_o2": factors.supplemental_o2,
            "temperature": factors.temperature,
            "systolic_bp": factors.systolic_bp,
            "heart_rate": factors.heart_rate,
            "consciousness": factors.consciousness,
        }
        for name, points in domains.items():
            if points < 0 or points > 3:
                raise ValueError(f"{name} must be between 0 and 3")
        score = sum(domains.values())
        positive = [k for k, v in domains.items() if v > 0]
        if score >= 7:
            band = "high"
            severity = Severity.HIGH
        elif score >= 5:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: News2EarlyWarningScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = News2EarlyWarningRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("news2_early_warning_scorer_scored", score=score, band=band)
        return [finding]
