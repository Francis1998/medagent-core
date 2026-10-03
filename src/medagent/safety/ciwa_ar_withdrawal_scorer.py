"""CiwaArWithdrawalScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ASAM / EHR CIWA-Ar alcohol withdrawal score gap for
offline medical-ward agent pipelines.
Distinct from ``GcsNeurologicStatusScorer / FallRiskChecker``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CiwaArWithdrawalRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CiwaArWithdrawalFactors:
    """Simplified CiwaArWithdrawalScorer factors."""

    nausea: int = 0
    tremor: int = 0
    anxiety: int = 0
    agitation: int = 0
    paroxysmal_sweats: int = 0
    orientation_deficit: int = 0


class CiwaArWithdrawalScorer:
    """Compute advisory CiwaArWithdrawalRisk findings."""

    def check(self, factors: CiwaArWithdrawalFactors) -> list[CiwaArWithdrawalRisk]:
        """Return one advisory finding."""

        binaries = {
            "nausea": factors.nausea,
            "tremor": factors.tremor,
            "anxiety": factors.anxiety,
            "agitation": factors.agitation,
            "paroxysmal_sweats": factors.paroxysmal_sweats,
            "orientation_deficit": factors.orientation_deficit,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 2:
            band = "low"
            severity = Severity.LOW
        elif score <= 4:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: CiwaArWithdrawalScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CiwaArWithdrawalRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ciwa_ar_withdrawal_scorer_scored", score=score, band=band)
        return [finding]
