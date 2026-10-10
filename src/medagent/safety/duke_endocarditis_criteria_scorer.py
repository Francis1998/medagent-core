"""DukeEndocarditisCriteriaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA modified Duke endocarditis criteria gap for
offline medical-ward agent pipelines.
Distinct from `CentorStrepPharyngitisScorer` / `JonesCriteriaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import DukeEndocarditisCriteriaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DukeEndocarditisCriteriaFactors:
    """Simplified DukeEndocarditisCriteriaScorer factors."""

    major_echo_ok: int = 0
    major_micro_ok: int = 0
    minor_fever_ok: int = 0
    minor_vascular_ok: int = 0
    minor_immuno_ok: int = 0


class DukeEndocarditisCriteriaScorer:
    """Compute advisory DukeEndocarditisCriteriaRisk findings."""

    def check(self, factors: DukeEndocarditisCriteriaFactors) -> list[DukeEndocarditisCriteriaRisk]:
        """Return one advisory finding."""

        binaries = {
            "major_echo_ok": factors.major_echo_ok,
            "major_micro_ok": factors.major_micro_ok,
            "minor_fever_ok": factors.minor_fever_ok,
            "minor_vascular_ok": factors.minor_vascular_ok,
            "minor_immuno_ok": factors.minor_immuno_ok,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 2:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: DukeEndocarditisCriteriaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = DukeEndocarditisCriteriaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("duke_endocarditis_criteria_scorer_scored", score=score, band=band)
        return [finding]
