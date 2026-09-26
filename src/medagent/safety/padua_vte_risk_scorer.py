"""PaduaVteRiskScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACCP / EHR Padua VTE risk gap for
offline medical-ward agent pipelines.
Distinct from ``CapriniVteRiskScorer / WellsPeProbabilityScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full Padua chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PaduaVteRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PaduaVteFactors:
    """Simplified Padua-style weighted factors."""

    active_cancer: int = 0  # 3 pts
    prior_vte: int = 0  # 3 pts
    reduced_mobility: int = 0  # 3 pts
    thrombophilia: int = 0  # 3 pts
    age_ge_70: int = 0  # 1 pt


class PaduaVteRiskScorer:
    """Compute advisory PaduaVteRisk findings."""

    def check(self, factors: PaduaVteFactors) -> list[PaduaVteRisk]:
        """Return one advisory finding."""

        binaries = {
            "active_cancer": factors.active_cancer,
            "prior_vte": factors.prior_vte,
            "reduced_mobility": factors.reduced_mobility,
            "thrombophilia": factors.thrombophilia,
            "age_ge_70": factors.age_ge_70,
        }
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        weights = {
            "active_cancer": 3,
            "prior_vte": 3,
            "reduced_mobility": 3,
            "thrombophilia": 3,
            "age_ge_70": 1,
        }
        score = sum(weights[k] for k, v in binaries.items() if v)
        positive = [k for k, v in binaries.items() if v > 0]
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
            "RESEARCH USE ONLY: PaduaVteRiskScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PaduaVteRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("padua_vte_risk_scorer_scored", score=score, band=band)
        return [finding]
