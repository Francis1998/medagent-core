"""CHA2DS2-VASc stroke-risk scorer (research-only clinical score).

Scores Congestive HF / Hypertension / Age / Diabetes / Stroke / Vascular /
Sex category factors into an advisory CHA2DS2-VASc total. Closes the MDCalc /
UpToDate / EHR embedded CHA2DS2-VASc calculator gap for offline agent
pipelines. Distinct from ``HasBledBleedRiskScorer`` (bleed risk) and
anticoagulant DDI checkers. Prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 for narrative summaries. Never modifies medications and never
performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Cha2ds2VascStrokeRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Cha2ds2VascFactors:
    """CHA2DS2-VASc input factors with standard point weights."""

    congestive_hf: bool = False
    hypertension: bool = False
    age_ge_75: bool = False
    age_65_to_74: bool = False
    diabetes: bool = False
    stroke_tia_thromboembolism: bool = False
    vascular_disease: bool = False
    female_sex: bool = False


class Cha2ds2VascStrokeRiskScorer:
    """Compute advisory CHA2DS2-VASc totals from clinical factors."""

    def check(self, factors: Cha2ds2VascFactors) -> list[Cha2ds2VascStrokeRisk]:
        """Return one advisory finding with the CHA2DS2-VASc total."""

        points: list[tuple[str, int]] = []
        if factors.congestive_hf:
            points.append(("congestive_hf", 1))
        if factors.hypertension:
            points.append(("hypertension", 1))
        if factors.age_ge_75:
            points.append(("age_ge_75", 2))
        elif factors.age_65_to_74:
            points.append(("age_65_to_74", 1))
        if factors.diabetes:
            points.append(("diabetes", 1))
        if factors.stroke_tia_thromboembolism:
            points.append(("stroke_tia_thromboembolism", 2))
        if factors.vascular_disease:
            points.append(("vascular_disease", 1))
        if factors.female_sex:
            points.append(("female_sex", 1))

        score = sum(weight for _, weight in points)
        positive = [name for name, _ in points]
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
            "RESEARCH USE ONLY: CHA2DS2-VASc total "
            f"{score} ({band}) from factors {positive or ['none']}. "
            "This advisory score never modifies anticoagulation; obtain "
            "qualified clinical review before therapy changes."
        )
        finding = Cha2ds2VascStrokeRisk(
            score=score,
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("cha2ds2_vasc_scored", score=score, band=band)
        return [finding]
