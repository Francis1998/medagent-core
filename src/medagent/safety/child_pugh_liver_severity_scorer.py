"""Child-Pugh liver-severity scorer (research-only clinical score).

Scores bilirubin / albumin / INR / ascites / encephalopathy categories into
an advisory Child-Pugh class (A/B/C). Closes the MDCalc / UpToDate / EHR
embedded Child-Pugh calculator gap for offline agent pipelines. Distinct from
``HasBledBleedRiskScorer`` and hepatic DDI checkers. Prefer GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries. Never
modifies medications and never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import ChildPughLiverSeverity, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ChildPughFactors:
    """Child-Pugh category points (each domain scored 1-3)."""

    bilirubin_points: int = 1
    albumin_points: int = 1
    inr_points: int = 1
    ascites_points: int = 1
    encephalopathy_points: int = 1


class ChildPughLiverSeverityScorer:
    """Compute advisory Child-Pugh totals and class A/B/C."""

    def check(self, factors: ChildPughFactors) -> list[ChildPughLiverSeverity]:
        """Return one advisory finding with Child-Pugh total and class."""

        domains = {
            "bilirubin": factors.bilirubin_points,
            "albumin": factors.albumin_points,
            "inr": factors.inr_points,
            "ascites": factors.ascites_points,
            "encephalopathy": factors.encephalopathy_points,
        }
        for name, points in domains.items():
            if points not in {1, 2, 3}:
                raise ValueError(f"{name}_points must be 1, 2, or 3")
        score = sum(domains.values())
        if score >= 10:
            child_class = "C"
            band = "severe"
            severity = Severity.HIGH
        elif score >= 7:
            child_class = "B"
            band = "moderate"
            severity = Severity.MODERATE
        else:
            child_class = "A"
            band = "mild"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: Child-Pugh total "
            f"{score} (class {child_class}, {band}) from domain points {domains}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = ChildPughLiverSeverity(
            score=score,
            child_class=child_class,
            band=band,
            domain_points=domains,
            severity=severity,
            rationale=rationale,
        )
        logger.info("child_pugh_scored", score=score, child_class=child_class)
        return [finding]
