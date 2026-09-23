"""WellsPeProbabilityScorer (research-only clinical score).

Advisory scorer closing the MDCalc / UpToDate / EHR Wells PE calculator gap for offline agent
pipelines.
Distinct from ``HasBledBleedRiskScorer / Cha2ds2VascStrokeRiskScorer``. Prefer GPT-5.5 / Claude
Sonnet 4.6 /
Gemini 3.x / Kimi K2 for narrative summaries. Never modifies medications and
never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, WellsPeProbability

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WellsPeFactors:
    """Input factors for WellsPeProbabilityScorer."""

    clinical_dvt_signs: bool = False
    pe_most_likely: bool = False
    heart_rate_over_100: bool = False
    immobilization_or_surgery: bool = False
    previous_dvt_pe: bool = False
    hemoptysis: bool = False
    malignancy: bool = False


class WellsPeProbabilityScorer:
    """Compute advisory WellsPeProbability findings."""

    def check(self, factors: WellsPeFactors) -> list[WellsPeProbability]:
        """Return one advisory finding."""

        items = [
            ("clinical_dvt_signs", factors.clinical_dvt_signs, 3.0),
            ("pe_most_likely", factors.pe_most_likely, 3.0),
            ("heart_rate_over_100", factors.heart_rate_over_100, 1.5),
            ("immobilization_or_surgery", factors.immobilization_or_surgery, 1.5),
            ("previous_dvt_pe", factors.previous_dvt_pe, 1.5),
            ("hemoptysis", factors.hemoptysis, 1.0),
            ("malignancy", factors.malignancy, 1.0),
        ]
        positive: list[str] = []
        score = 0.0
        for name, present, pts in items:
            if present:
                positive.append(name)
                score += pts
        score = float(score)

        if score >= 6.0:
            band = "high"
            severity = Severity.HIGH
        elif score >= 2.0:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW

        rationale = (
            "RESEARCH USE ONLY: WellsPeProbabilityScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = WellsPeProbability(
            score=float(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("wells_pe_probability_scorer_scored", score=score, band=band)
        return [finding]
