"""Warfarin + nitroimidazole antibiotic interaction safety checker.

Metronidazole and tinidazole can inhibit CYP2C9-mediated warfarin
metabolism, increasing INR and bleeding risk. This focused control is
distinct from warfarin + azole, fluoroquinolone, amiodarone, and NSAID
interaction checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, WarfarinMetronidazoleRisk

logger = get_logger(__name__)

_WARFARIN_AGENTS: Final[dict[str, str]] = {
    "warfarin": "a vitamin K antagonist anticoagulant",
    "coumadin": "a warfarin brand formulation",
    "jantoven": "a warfarin brand formulation",
}

_NITROIMIDAZOLE_AGENTS: Final[dict[str, str]] = {
    "metronidazole": "a nitroimidazole antibiotic that inhibits CYP2C9",
    "tinidazole": "a nitroimidazole antibiotic with a warfarin interaction",
}


class WarfarinMetronidazoleChecker:
    """Flag warfarin co-prescribed with metronidazole or tinidazole."""

    def check(
        self, medications: list[Medication]
    ) -> list[WarfarinMetronidazoleRisk]:
        """Return one finding per unique warfarin × nitroimidazole pair."""
        warfarin_matches: list[tuple[int, Medication, str]] = []
        nitroimidazole_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            warfarin_candidates = sorted(tokens & set(_WARFARIN_AGENTS))
            if warfarin_candidates:
                warfarin_matches.append(
                    (index, medication, warfarin_candidates[0])
                )

            antibiotic_candidates = sorted(
                tokens & set(_NITROIMIDAZOLE_AGENTS)
            )
            if antibiotic_candidates:
                nitroimidazole_matches.append(
                    (index, medication, antibiotic_candidates[0])
                )

        if not warfarin_matches or not nitroimidazole_matches:
            logger.info("warfarin_metronidazole_checked", findings=0)
            return []

        warfarin_matches.sort(
            key=lambda match: (match[1].name.lower(), match[2], match[0])
        )
        nitroimidazole_matches.sort(
            key=lambda match: (match[1].name.lower(), match[2], match[0])
        )
        findings: list[WarfarinMetronidazoleRisk] = []
        seen: set[tuple[str, str]] = set()

        for warfarin_index, warfarin_med, warfarin_agent in warfarin_matches:
            for antibiotic_index, antibiotic_med, antibiotic_agent in (
                nitroimidazole_matches
            ):
                pair_key = (warfarin_agent, antibiotic_agent)
                if warfarin_index == antibiotic_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    WarfarinMetronidazoleRisk(
                        medication=warfarin_med.name,
                        agent=warfarin_agent,
                        partner_medication=antibiotic_med.name,
                        partner_agent=antibiotic_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            warfarin_medication=warfarin_med.name,
                            warfarin_agent=warfarin_agent,
                            antibiotic_medication=antibiotic_med.name,
                            antibiotic_agent=antibiotic_agent,
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
        logger.info(
            "warfarin_metronidazole_checked", findings=len(findings)
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        warfarin_medication: str,
        warfarin_agent: str,
        antibiotic_medication: str,
        antibiotic_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{warfarin_medication}' contains {warfarin_agent}, "
            f"{_WARFARIN_AGENTS[warfarin_agent]}, and is co-prescribed with "
            f"'{antibiotic_medication}' ({antibiotic_agent}, "
            f"{_NITROIMIDAZOLE_AGENTS[antibiotic_agent]}). CYP2C9 inhibition "
            "may reduce warfarin clearance, elevate INR, and increase bleeding "
            "risk. Promptly review alternatives and arrange closer INR "
            "monitoring with a qualified clinician; do not change therapy from "
            "this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
