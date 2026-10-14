"""RemsPeSeverityScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ESC REMs PE severity screen gap for
offline medical-ward agent pipelines.
Distinct from `PesiPeSeverityScorer` / `WellsPeProbabilityScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RemsPeSeverityRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RemsPeSeverityFactors:
    """Simplified RemsPeSeverityScorer factors."""

    rv_strain_ok: int = 0
    troponin_ok: int = 0
    bnp_ok: int = 0
    hypotension_ok: int = 0


class RemsPeSeverityScorer:
    """Compute advisory RemsPeSeverityRisk findings."""

    def check(self, factors: RemsPeSeverityFactors) -> list[RemsPeSeverityRisk]:
        """Return one advisory finding."""

        binaries = {
            "rv_strain_ok": factors.rv_strain_ok,
            "troponin_ok": factors.troponin_ok,
            "bnp_ok": factors.bnp_ok,
            "hypotension_ok": factors.hypotension_ok,
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
            "RESEARCH USE ONLY: RemsPeSeverityScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RemsPeSeverityRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("rems_pe_severity_scorer_scored", score=score, band=band)
        return [finding]
