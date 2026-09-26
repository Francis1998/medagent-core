"""PsiPortPneumoniaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ATS / EHR PSI/PORT pneumonia severity
gap for offline agent pipelines.
Distinct from ``Curb65PneumoniaScorer / SofaOrganFailureScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full PSI chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PsiPortPneumoniaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PsiPortFactors:
    """Simplified PSI/PORT-style weighted factors."""

    age_ge_70: int = 0  # 2 pts
    nursing_home: int = 0  # 2 pts
    neoplastic: int = 0  # 3 pts
    respiratory_rate_ge_30: int = 0  # 2 pts
    bun_ge_30: int = 0  # 2 pts


class PsiPortPneumoniaScorer:
    """Compute advisory PsiPortPneumoniaRisk findings."""

    def check(self, factors: PsiPortFactors) -> list[PsiPortPneumoniaRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_70": factors.age_ge_70,
            "nursing_home": factors.nursing_home,
            "neoplastic": factors.neoplastic,
            "respiratory_rate_ge_30": factors.respiratory_rate_ge_30,
            "bun_ge_30": factors.bun_ge_30,
        }
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")
        weights = {
            "age_ge_70": 2,
            "nursing_home": 2,
            "neoplastic": 3,
            "respiratory_rate_ge_30": 2,
            "bun_ge_30": 2,
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
            "RESEARCH USE ONLY: PsiPortPneumoniaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PsiPortPneumoniaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("psi_port_pneumonia_scorer_scored", score=score, band=band)
        return [finding]
