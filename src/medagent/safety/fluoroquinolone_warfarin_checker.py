"""Fluoroquinolone + warfarin INR and bleeding-risk safety checker.

Fluoroquinolone antibiotics can potentiate warfarin anticoagulation, increasing
INR variability and bleeding risk. This hazard is distinct from amiodarone +
warfarin INR potentiation, warfarin + NSAID bleeding intensification, and
generic drug-drug interaction screening.

This checker flags ciprofloxacin, levofloxacin, moxifloxacin, or ofloxacin
co-prescribed with warfarin-class anticoagulants. Whole-token matching is used
throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import FluoroquinoloneWarfarinRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_FLUOROQUINOLONE_AGENTS: Final[dict[str, str]] = {
    "ciprofloxacin": "a fluoroquinolone antibiotic associated with INR elevation",
    "levofloxacin": "a fluoroquinolone antibiotic associated with INR elevation",
    "moxifloxacin": "a fluoroquinolone antibiotic associated with INR elevation",
    "ofloxacin": "a fluoroquinolone antibiotic associated with INR elevation",
}

_WARFARIN_AGENTS: Final[dict[str, str]] = {
    "warfarin": "a vitamin K antagonist anticoagulant",
    "coumadin": "a warfarin brand formulation (vitamin K antagonist)",
    "jantoven": "a warfarin brand formulation (vitamin K antagonist)",
}


class FluoroquinoloneWarfarinChecker:
    """Flag fluoroquinolones co-prescribed with warfarin-class agents."""

    def check(self, medications: list[Medication]) -> list[FluoroquinoloneWarfarinRisk]:
        """Return one finding per unique fluoroquinolone × warfarin pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        fluoroquinolone_matches: list[tuple[int, Medication, str]] = []
        warfarin_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            fluoroquinolone_candidates = sorted(tokens & set(_FLUOROQUINOLONE_AGENTS))
            if fluoroquinolone_candidates:
                fluoroquinolone_matches.append((index, medication, fluoroquinolone_candidates[0]))

            warfarin_candidates = sorted(tokens & set(_WARFARIN_AGENTS))
            if warfarin_candidates:
                warfarin_matches.append((index, medication, warfarin_candidates[0]))

        if not fluoroquinolone_matches or not warfarin_matches:
            logger.info("fluoroquinolone_warfarin_checked", findings=0)
            return []

        fluoroquinolone_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        warfarin_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[FluoroquinoloneWarfarinRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for (
            fluoroquinolone_index,
            fluoroquinolone_med,
            fluoroquinolone_agent,
        ) in fluoroquinolone_matches:
            fluoroquinolone_desc = _FLUOROQUINOLONE_AGENTS[fluoroquinolone_agent]
            for warfarin_index, warfarin_med, warfarin_agent in warfarin_matches:
                if fluoroquinolone_index == warfarin_index:
                    continue
                pair_key = (fluoroquinolone_agent, warfarin_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    FluoroquinoloneWarfarinRisk(
                        medication=fluoroquinolone_med.name,
                        agent=fluoroquinolone_agent,
                        partner_medication=warfarin_med.name,
                        partner_agent=warfarin_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            fluoroquinolone_medication=fluoroquinolone_med.name,
                            fluoroquinolone_agent=fluoroquinolone_agent,
                            fluoroquinolone_descriptor=fluoroquinolone_desc,
                            warfarin_medication=warfarin_med.name,
                            warfarin_agent=warfarin_agent,
                            warfarin_descriptor=_WARFARIN_AGENTS[warfarin_agent],
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                finding.partner_medication.lower(),
                finding.agent,
                finding.partner_agent,
            )
        )
        logger.info(
            "fluoroquinolone_warfarin_checked",
            findings=len(findings),
            fluoroquinolone_agents=len(
                {agent for _index, _medication, agent in fluoroquinolone_matches}
            ),
            warfarin_agents=len({agent for _index, _medication, agent in warfarin_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        fluoroquinolone_medication: str,
        fluoroquinolone_agent: str,
        fluoroquinolone_descriptor: str,
        warfarin_medication: str,
        warfarin_agent: str,
        warfarin_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY fluoroquinolone × warfarin rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{fluoroquinolone_medication}' contains "
            f"{fluoroquinolone_agent}, {fluoroquinolone_descriptor}, and is "
            f"co-prescribed with '{warfarin_medication}' ({warfarin_agent}, "
            f"{warfarin_descriptor}). Fluoroquinolones can potentiate warfarin "
            "anticoagulation, increase INR variability, and increase bleeding risk. "
            "Promptly review the combination and INR monitoring plan with a "
            "qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
