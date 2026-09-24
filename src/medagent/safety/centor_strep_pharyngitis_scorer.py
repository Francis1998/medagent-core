"""CentorStrepPharyngitisScorer (research-only clinical score).

Advisory scorer closing the MDCalc / IDSA / EHR Centor strep calculator gap for
offline agent pipelines.
Distinct from ``Curb65PneumoniaScorer / AntibioticStewardshipChecker``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CentorStrepPharyngitisRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CentorStrepPharyngitisFactors:
    """Modified Centor / McIsaac binary factors (0/1 each)."""

    tonsillar_exudate: int = 0
    tender_anterior_nodes: int = 0
    fever_history: int = 0
    cough_absent: int = 0
    age_bonus: int = 0  # McIsaac: +1 age 3-14, 0 age 15-44, -1 age >=45 encoded as 0/1/0


class CentorStrepPharyngitisScorer:
    """Compute advisory CentorStrepPharyngitisRisk findings."""

    def check(self, factors: CentorStrepPharyngitisFactors) -> list[CentorStrepPharyngitisRisk]:
        """Return one advisory finding."""

        domains = {
            "tonsillar_exudate": factors.tonsillar_exudate,
            "tender_anterior_nodes": factors.tender_anterior_nodes,
            "fever_history": factors.fever_history,
            "cough_absent": factors.cough_absent,
            "age_bonus": factors.age_bonus,
        }
        for name, points in domains.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        score = sum(domains.values())
        positive = [k for k, v in domains.items() if v > 0]
        if score >= 4:
            band = "high"
            severity = Severity.HIGH
        elif score >= 2:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: CentorStrepPharyngitisScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CentorStrepPharyngitisRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("centor_strep_pharyngitis_scorer_scored", score=score, band=band)
        return [finding]
