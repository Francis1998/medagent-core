"""Lithium + thiazide diuretic toxicity safety checker.

Thiazide and thiazide-like diuretics can reduce renal lithium clearance,
raise serum lithium concentrations, and cause toxicity. This focused
control is distinct from lithium + NSAID and lithium + ACEI/ARB checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import LithiumThiazideRisk, Medication, Severity

logger = get_logger(__name__)

_LITHIUM_AGENTS: Final[dict[str, str]] = {
    "lithium": "a mood stabilizer with a narrow therapeutic index",
    "lithobid": "a lithium brand formulation with a narrow therapeutic index",
    "eskalith": "a lithium brand formulation with a narrow therapeutic index",
}

_THIAZIDE_AGENTS: Final[dict[str, str]] = {
    "hctz": "an abbreviation for the thiazide diuretic hydrochlorothiazide",
    "hydrochlorothiazide": "a thiazide diuretic",
    "chlorthalidone": "a thiazide-like diuretic",
    "indapamide": "a thiazide-like diuretic",
}


class LithiumThiazideChecker:
    """Flag lithium co-prescribed with thiazide(-like) diuretics."""

    def check(self, medications: list[Medication]) -> list[LithiumThiazideRisk]:
        """Return one finding per unique lithium × thiazide pair."""
        lithium_matches: list[tuple[int, Medication, str]] = []
        thiazide_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            lithium_candidates = sorted(tokens & set(_LITHIUM_AGENTS))
            if lithium_candidates:
                lithium_matches.append((index, medication, lithium_candidates[0]))

            thiazide_candidates = sorted(tokens & set(_THIAZIDE_AGENTS))
            if thiazide_candidates:
                thiazide_matches.append((index, medication, thiazide_candidates[0]))

        if not lithium_matches or not thiazide_matches:
            logger.info("lithium_thiazide_checked", findings=0)
            return []

        lithium_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        thiazide_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[LithiumThiazideRisk] = []
        seen: set[tuple[str, str]] = set()

        for lithium_index, lithium_med, lithium_agent in lithium_matches:
            for thiazide_index, thiazide_med, thiazide_agent in thiazide_matches:
                pair_key = (lithium_agent, thiazide_agent)
                if lithium_index == thiazide_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    LithiumThiazideRisk(
                        medication=lithium_med.name,
                        agent=lithium_agent,
                        partner_medication=thiazide_med.name,
                        partner_agent=thiazide_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            lithium_medication=lithium_med.name,
                            lithium_agent=lithium_agent,
                            thiazide_medication=thiazide_med.name,
                            thiazide_agent=thiazide_agent,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                finding.medication.lower(),
                finding.partner_medication.lower(),
                finding.agent,
                finding.partner_agent,
            )
        )
        logger.info("lithium_thiazide_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        lithium_medication: str,
        lithium_agent: str,
        thiazide_medication: str,
        thiazide_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{lithium_medication}' contains {lithium_agent}, "
            f"{_LITHIUM_AGENTS[lithium_agent]}, and is co-prescribed with "
            f"'{thiazide_medication}' ({thiazide_agent}, "
            f"{_THIAZIDE_AGENTS[thiazide_agent]}). Thiazide-related sodium "
            "loss can increase proximal lithium reabsorption, reduce renal "
            "lithium clearance, raise serum concentrations, and cause "
            "toxicity. Promptly review alternatives, lithium levels, renal "
            "function, and hydration with a qualified clinician; do not "
            "change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
