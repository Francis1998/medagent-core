"""HAS-BLED bleed-risk scorer (research-only clinical score).

Scores Hypertension / Abnormal renal-liver / Stroke / Bleeding history /
Labile INR / Elderly / Drugs-alcohol factors into an advisory HAS-BLED total.
Closes the MDCalc / UpToDate / EHR embedded HAS-BLED calculator gap for
offline agent pipelines. Distinct from ``AnticoagBleedingChecker`` (DDI/
stack panels) and ``AnticoagBleedStackPanel``. Prefer GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries. Never
modifies medications and never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import HasBledBleedRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HasBledFactors:
    """Boolean HAS-BLED input factors (each worth 1 point when True)."""

    hypertension: bool = False
    abnormal_renal: bool = False
    abnormal_liver: bool = False
    stroke_history: bool = False
    bleeding_history: bool = False
    labile_inr: bool = False
    elderly: bool = False
    drugs: bool = False
    alcohol: bool = False


class HasBledBleedRiskScorer:
    """Compute advisory HAS-BLED totals from clinical factors."""

    def check(self, factors: HasBledFactors) -> list[HasBledBleedRisk]:
        """Return one advisory finding with the HAS-BLED total.

        Args:
            factors: Boolean HAS-BLED component flags.

        Returns:
            A single-item list with score, band, severity, and rationale.
        """

        components = {
            "hypertension": factors.hypertension,
            "abnormal_renal": factors.abnormal_renal,
            "abnormal_liver": factors.abnormal_liver,
            "stroke_history": factors.stroke_history,
            "bleeding_history": factors.bleeding_history,
            "labile_inr": factors.labile_inr,
            "elderly": factors.elderly,
            "drugs": factors.drugs,
            "alcohol": factors.alcohol,
        }
        positive = [name for name, flag in components.items() if flag]
        score = len(positive)
        if score >= 3:
            band = "high"
            severity = Severity.HIGH
        elif score == 2:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: HAS-BLED total "
            f"{score} ({band}) from factors {positive or ['none']}. "
            "This advisory score never modifies anticoagulation; obtain "
            "qualified clinical review before therapy changes."
        )
        finding = HasBledBleedRisk(
            score=score,
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("has_bled_scored", score=score, band=band)
        return [finding]
