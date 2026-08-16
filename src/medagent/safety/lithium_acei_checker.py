"""Lithium + ACE inhibitor/ARB toxicity safety checker.

ACE inhibitors and ARBs may reduce renal lithium clearance, increasing serum
lithium concentrations and toxicity risk. This focused hazard is distinct from
ACEI/ARB duplication, ACEI/ARB + trimethoprim, and lithium + NSAID controls.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import LithiumAceiRisk, Medication, Severity

logger = get_logger(__name__)

_LITHIUM_AGENTS: Final[dict[str, str]] = {
    "lithium": "a mood stabilizer with a narrow therapeutic index",
    "lithobid": "a lithium brand formulation with a narrow therapeutic index",
    "eskalith": "a lithium brand formulation with a narrow therapeutic index",
}

_ACEI_ARB_AGENTS: Final[dict[str, str]] = {
    "lisinopril": "an ACE inhibitor",
    "enalapril": "an ACE inhibitor",
    "ramipril": "an ACE inhibitor",
    "benazepril": "an ACE inhibitor",
    "quinapril": "an ACE inhibitor",
    "captopril": "an ACE inhibitor",
    "fosinopril": "an ACE inhibitor",
    "perindopril": "an ACE inhibitor",
    "trandolapril": "an ACE inhibitor",
    "moexipril": "an ACE inhibitor",
    "losartan": "an angiotensin receptor blocker",
    "valsartan": "an angiotensin receptor blocker",
    "olmesartan": "an angiotensin receptor blocker",
    "candesartan": "an angiotensin receptor blocker",
    "irbesartan": "an angiotensin receptor blocker",
    "telmisartan": "an angiotensin receptor blocker",
    "azilsartan": "an angiotensin receptor blocker",
}


class LithiumAceiChecker:
    """Flag lithium co-prescribed with an ACE inhibitor or ARB."""

    def check(self, medications: list[Medication]) -> list[LithiumAceiRisk]:
        """Return one finding per unique lithium × ACEI/ARB pair."""
        lithium_matches: list[tuple[int, Medication, str]] = []
        raas_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            lithium_candidates = sorted(tokens & set(_LITHIUM_AGENTS))
            if lithium_candidates:
                lithium_matches.append((index, medication, lithium_candidates[0]))
            raas_candidates = sorted(tokens & set(_ACEI_ARB_AGENTS))
            if raas_candidates:
                raas_matches.append((index, medication, raas_candidates[0]))

        if not lithium_matches or not raas_matches:
            logger.info("lithium_acei_checked", findings=0)
            return []

        lithium_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        raas_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[LithiumAceiRisk] = []
        seen: set[tuple[str, str]] = set()

        for lithium_index, lithium_med, lithium_agent in lithium_matches:
            for raas_index, raas_med, raas_agent in raas_matches:
                if lithium_index == raas_index or (lithium_agent, raas_agent) in seen:
                    continue
                seen.add((lithium_agent, raas_agent))
                findings.append(
                    LithiumAceiRisk(
                        medication=lithium_med.name,
                        agent=lithium_agent,
                        partner_medication=raas_med.name,
                        partner_agent=raas_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            lithium_med.name,
                            lithium_agent,
                            raas_med.name,
                            raas_agent,
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
        logger.info("lithium_acei_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        lithium_medication: str,
        lithium_agent: str,
        raas_medication: str,
        raas_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{lithium_medication}' contains {lithium_agent}, "
            f"{_LITHIUM_AGENTS[lithium_agent]}, and is co-prescribed with "
            f"'{raas_medication}' ({raas_agent}, {_ACEI_ARB_AGENTS[raas_agent]}). "
            "ACE inhibitors and ARBs may reduce renal lithium clearance, increase "
            "serum lithium concentrations, and cause lithium toxicity. Review lithium "
            "levels, renal function, hydration, and alternatives with a qualified "
            "clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
