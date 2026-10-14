"""SmartCopPneumoniaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / IDSA SMART-COP pneumonia severity screen gap for
offline medical-ward agent pipelines.
Distinct from `Curb65PneumoniaScorer` / `PsiPortPneumoniaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, SmartCopPneumoniaRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SmartCopPneumoniaFactors:
    """Simplified SmartCopPneumoniaScorer factors."""

    sbp_ok: int = 0
    multilobar_ok: int = 0
    albumin_ok: int = 0
    rr_ok: int = 0
    tachycardia_ok: int = 0
    confusion_ok: int = 0
    oxygenation_ok: int = 0
    ph_ok: int = 0


class SmartCopPneumoniaScorer:
    """Compute advisory SmartCopPneumoniaRisk findings."""

    def check(self, factors: SmartCopPneumoniaFactors) -> list[SmartCopPneumoniaRisk]:
        """Return one advisory finding."""

        binaries = {
            "sbp_ok": factors.sbp_ok,
            "multilobar_ok": factors.multilobar_ok,
            "albumin_ok": factors.albumin_ok,
            "rr_ok": factors.rr_ok,
            "tachycardia_ok": factors.tachycardia_ok,
            "confusion_ok": factors.confusion_ok,
            "oxygenation_ok": factors.oxygenation_ok,
            "ph_ok": factors.ph_ok,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= max(2, len(binaries) // 2):
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: SmartCopPneumoniaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = SmartCopPneumoniaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("smart_cop_pneumonia_scorer_scored", score=score, band=band)
        return [finding]
