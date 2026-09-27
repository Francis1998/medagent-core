"""AlvaradoAppendicitisScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AAOS / EHR Alvarado appendicitis score
gap for offline medical-ward agent pipelines.
Distinct from ``OttawaAnkleRuleScorer / CentorStrepPharyngitisScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full Alvarado chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import AlvaradoAppendicitisRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AlvaradoAppendicitisFactors:
    """Simplified Alvarado-style weighted factors."""

    migration: int = 0  # 1 pt
    anorexia: int = 0  # 1 pt
    nausea_vomiting: int = 0  # 1 pt
    rlq_tenderness: int = 0  # 2 pts
    rebound: int = 0  # 1 pt
    fever: int = 0  # 1 pt
    leukocytosis: int = 0  # 2 pts


class AlvaradoAppendicitisScorer:
    """Compute advisory AlvaradoAppendicitisRisk findings."""

    def check(self, factors: AlvaradoAppendicitisFactors) -> list[AlvaradoAppendicitisRisk]:
        """Return one advisory finding."""

        binaries = {
            "migration": factors.migration,
            "anorexia": factors.anorexia,
            "nausea_vomiting": factors.nausea_vomiting,
            "rlq_tenderness": factors.rlq_tenderness,
            "rebound": factors.rebound,
            "fever": factors.fever,
            "leukocytosis": factors.leukocytosis,
        }
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        weights = {
            "migration": 1,
            "anorexia": 1,
            "nausea_vomiting": 1,
            "rlq_tenderness": 2,
            "rebound": 1,
            "fever": 1,
            "leukocytosis": 2,
        }
        score = sum(weights[k] for k, v in binaries.items() if v)
        positive = [k for k, v in binaries.items() if v > 0]
        if score >= 7:
            band = "high"
            severity = Severity.HIGH
        elif score >= 4:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: AlvaradoAppendicitisScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = AlvaradoAppendicitisRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("alvarado_appendicitis_scorer_scored", score=score, band=band)
        return [finding]
