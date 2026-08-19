"""Carbamazepine + CYP3A4-inhibiting macrolide safety checker.

Clarithromycin and erythromycin inhibit CYP3A4-mediated carbamazepine
metabolism, raising carbamazepine exposure and toxicity risk. Azithromycin is
intentionally excluded because it does not typically cause this interaction.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import CarbamazepineMacrolideRisk, Medication, Severity

logger = get_logger(__name__)

_CARBAMAZEPINE_AGENTS: Final[dict[str, str]] = {
    "carbamazepine": "an antiseizure medication with a narrow therapeutic index",
    "tegretol": "a carbamazepine brand formulation with a narrow therapeutic index",
    "carbatrol": "a carbamazepine brand formulation with a narrow therapeutic index",
    "equetro": "a carbamazepine brand formulation with a narrow therapeutic index",
}

_MACROLIDE_AGENTS: Final[dict[str, str]] = {
    "clarithromycin": "a macrolide antibiotic and strong CYP3A4 inhibitor",
    "erythromycin": "a macrolide antibiotic and strong CYP3A4 inhibitor",
}


class CarbamazepineMacrolideChecker:
    """Flag carbamazepine co-prescribed with CYP3A4-inhibiting macrolides."""

    def check(self, medications: list[Medication]) -> list[CarbamazepineMacrolideRisk]:
        """Return one finding per unique carbamazepine × macrolide pair."""
        carbamazepine_matches: list[tuple[int, Medication, str]] = []
        macrolide_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            carbamazepine_candidates = sorted(tokens & set(_CARBAMAZEPINE_AGENTS))
            if carbamazepine_candidates:
                carbamazepine_matches.append((index, medication, carbamazepine_candidates[0]))

            macrolide_candidates = sorted(tokens & set(_MACROLIDE_AGENTS))
            if macrolide_candidates:
                macrolide_matches.append((index, medication, macrolide_candidates[0]))

        if not carbamazepine_matches or not macrolide_matches:
            logger.info("carbamazepine_macrolide_checked", findings=0)
            return []

        carbamazepine_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        macrolide_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[CarbamazepineMacrolideRisk] = []
        seen: set[tuple[str, str]] = set()

        for carb_index, carb_med, carb_agent in carbamazepine_matches:
            for macrolide_index, macrolide_med, macrolide_agent in macrolide_matches:
                pair_key = (carb_agent, macrolide_agent)
                if carb_index == macrolide_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    CarbamazepineMacrolideRisk(
                        medication=carb_med.name,
                        agent=carb_agent,
                        partner_medication=macrolide_med.name,
                        partner_agent=macrolide_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            carbamazepine_medication=carb_med.name,
                            carbamazepine_agent=carb_agent,
                            macrolide_medication=macrolide_med.name,
                            macrolide_agent=macrolide_agent,
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
        logger.info("carbamazepine_macrolide_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        carbamazepine_medication: str,
        carbamazepine_agent: str,
        macrolide_medication: str,
        macrolide_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{carbamazepine_medication}' contains {carbamazepine_agent}, "
            f"{_CARBAMAZEPINE_AGENTS[carbamazepine_agent]}, and is co-prescribed with "
            f"'{macrolide_medication}' ({macrolide_agent}, "
            f"{_MACROLIDE_AGENTS[macrolide_agent]}). CYP3A4 inhibition can reduce "
            "carbamazepine metabolism, raise serum concentrations, and cause neurologic "
            "or other dose-related toxicity. Promptly review alternatives, carbamazepine "
            "dose, and serum-level monitoring with a qualified clinician; do not change "
            "therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
