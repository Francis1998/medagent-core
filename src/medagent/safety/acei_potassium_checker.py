"""ACE inhibitor/ARB + potassium supplement hyperkalemia checker.

ACE inhibitors and angiotensin receptor blockers reduce aldosterone-mediated
potassium excretion; co-prescribed potassium chloride or other potassium
supplements increase hyperkalemia risk. This focused control is distinct
from ACEI/ARB + potassium-sparing diuretic (#3.60) and ACEI/ARB +
trimethoprim (#3.63) screening.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AceiPotassiumRisk, Medication, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "lisinopril": "an angiotensin-converting enzyme inhibitor",
    "enalapril": "an angiotensin-converting enzyme inhibitor",
    "ramipril": "an angiotensin-converting enzyme inhibitor",
    "benazepril": "an angiotensin-converting enzyme inhibitor",
    "captopril": "an angiotensin-converting enzyme inhibitor",
    "fosinopril": "an angiotensin-converting enzyme inhibitor",
    "perindopril": "an angiotensin-converting enzyme inhibitor",
    "quinapril": "an angiotensin-converting enzyme inhibitor",
    "trandolapril": "an angiotensin-converting enzyme inhibitor",
    "losartan": "an angiotensin II receptor blocker",
    "valsartan": "an angiotensin II receptor blocker",
    "candesartan": "an angiotensin II receptor blocker",
    "irbesartan": "an angiotensin II receptor blocker",
    "olmesartan": "an angiotensin II receptor blocker",
    "telmisartan": "an angiotensin II receptor blocker",
    "azilsartan": "an angiotensin II receptor blocker",
    "eprosartan": "an angiotensin II receptor blocker",
}

_PARTNER_AGENTS: Final[dict[str, str]] = {
    "potassium-chloride": "a potassium chloride supplement",
    "potassium": "a potassium supplement",
    "kcl": "a potassium chloride supplement",
    "klor-con": "a potassium chloride brand formulation",
}


class AceiPotassiumChecker:
    """Flag ACEI/ARB therapy co-prescribed with potassium supplementation."""

    def check(self, medications: list[Medication]) -> list[AceiPotassiumRisk]:
        """Return one finding per unique ACEI/ARB × potassium-supplement pair."""
        primary_matches: list[tuple[int, Medication, str]] = []
        partner_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            primary_agent = self._match_agent(medication.name, _PRIMARY_AGENTS)
            if primary_agent is not None:
                primary_matches.append((index, medication, primary_agent))

            partner_agent = self._match_agent(medication.name, _PARTNER_AGENTS)
            if partner_agent is not None:
                partner_matches.append((index, medication, partner_agent))

        if not primary_matches or not partner_matches:
            logger.info("acei_potassium_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[AceiPotassiumRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    AceiPotassiumRisk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            primary_medication=primary_med.name,
                            primary_agent=primary_agent,
                            partner_medication=partner_med.name,
                            partner_agent=partner_agent,
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
        logger.info("acei_potassium_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        primary_medication: str,
        primary_agent: str,
        partner_medication: str,
        partner_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{primary_medication}' contains {primary_agent}, "
            f"{_PRIMARY_AGENTS[primary_agent]}, and is co-prescribed with "
            f"'{partner_medication}' ({partner_agent}, "
            f"{_PARTNER_AGENTS[partner_agent]}). ACEI/ARB therapy plus "
            "exogenous potassium supplementation increases hyperkalemia risk. "
            "Promptly review serum potassium, renal function, and the need for "
            "supplementation with a qualified clinician; do not change therapy "
            "from this research output."
        )

    @staticmethod
    def _match_agent(name: str, agents: dict[str, str]) -> str | None:
        """Return the most specific whole-token/whole-alias match in ``name``."""
        lowered = name.lower()
        aliases = sorted(agents, key=lambda alias: (-len(alias.split("-")), alias))
        for alias in aliases:
            components = [re.escape(component) for component in alias.split("-")]
            pattern = r"(?<![a-z0-9])" + r"[\s_-]+".join(components) + r"(?![a-z0-9])"
            if re.search(pattern, lowered):
                return alias
        return None
