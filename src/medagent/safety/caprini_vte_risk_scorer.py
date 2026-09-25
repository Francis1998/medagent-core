"""CapriniVteRiskScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACCP / EHR Caprini VTE risk gap for
offline agent pipelines.
Distinct from ``WellsPeProbabilityScorer / HasBledBleedRiskScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full Caprini chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CapriniVteRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CapriniVteFactors:
    """Simplified Caprini-style weighted factors."""

    age_ge_75: int = 0  # 3 pts when 1
    major_surgery: int = 0  # 2 pts when 1
    malignancy: int = 0  # 2 pts when 1
    prior_vte: int = 0  # 3 pts when 1
    mobility_limited: int = 0  # 1 pt when 1


class CapriniVteRiskScorer:
    """Compute advisory CapriniVteRisk findings."""

    def check(self, factors: CapriniVteFactors) -> list[CapriniVteRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_75": factors.age_ge_75,
            "major_surgery": factors.major_surgery,
            "malignancy": factors.malignancy,
            "prior_vte": factors.prior_vte,
            "mobility_limited": factors.mobility_limited,
        }
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        weights = {
            "age_ge_75": 3,
            "major_surgery": 2,
            "malignancy": 2,
            "prior_vte": 3,
            "mobility_limited": 1,
        }
        score = sum(weights[k] for k, v in binaries.items() if v)
        positive = [k for k, v in binaries.items() if v > 0]
        if score >= 5:
            band = "high"
            severity = Severity.HIGH
        elif score >= 3:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: CapriniVteRiskScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CapriniVteRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("caprini_vte_risk_scorer_scored", score=score, band=band)
        return [finding]
