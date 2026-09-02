"""Apixaban + Strong CYP3A4/P-gp Inhibitor Risk.

Apixaban is a CYP3A4/P-gp substrate; strong inhibitors (ketoconazole, itraconazole,
ritonavir) raise exposure and bleeding risk. Distinct from dabigatran P-gp and DOAC
inducer checkers.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import ApixabanCyp3a4Risk, Medication, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "apixaban": "a factor Xa inhibitor DOAC metabolized by CYP3A4/P-gp",
    "eliquis": "an apixaban brand factor Xa inhibitor DOAC",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ketoconazole": (
        "a strong CYP3A4/P-gp inhibiting azole antifungal",
        Severity.CRITICAL,
    ),
    "nizoral": (
        "a ketoconazole brand strong CYP3A4/P-gp inhibiting azole",
        Severity.CRITICAL,
    ),
    "itraconazole": (
        "a strong CYP3A4/P-gp inhibiting azole antifungal",
        Severity.CRITICAL,
    ),
    "sporanox": (
        "an itraconazole brand strong CYP3A4/P-gp inhibiting azole",
        Severity.CRITICAL,
    ),
    "ritonavir": (
        "an HIV protease inhibitor and strong CYP3A4/P-gp inhibitor",
        Severity.CRITICAL,
    ),
    "norvir": (
        "a ritonavir brand strong CYP3A4/P-gp inhibitor",
        Severity.CRITICAL,
    ),
}

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class ApixabanCyp3a4Checker:
    """Flag Apixaban + Strong CYP3A4/P-gp pairs."""

    def check(self, medications: list[Medication]) -> list[ApixabanCyp3a4Risk]:
        """Return one finding per unique primary x partner pair."""
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
            logger.info("apixaban_cyp3a4_checker_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[ApixabanCyp3a4Risk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    ApixabanCyp3a4Risk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=severity,
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
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                finding.partner_medication.lower(),
                finding.agent,
                finding.partner_agent,
            )
        )
        logger.info("apixaban_cyp3a4_checker_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        primary_medication: str,
        primary_agent: str,
        partner_medication: str,
        partner_agent: str,
    ) -> str:
        partner_descriptor, _severity = _PARTNER_AGENTS[partner_agent]
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{primary_medication}' contains {primary_agent}, "
            f"{_PRIMARY_AGENTS[primary_agent]}, and is co-prescribed with "
            f"'{partner_medication}' ({partner_agent}, {partner_descriptor}). "
            "Strong CYP3A4 inhibition by clarithromycin can markedly increase "
            "amlodipine exposure and precipitate hypotension or shock, especially in "
            "older adults."
            " Promptly review with a qualified clinician; do not change therapy "
            "from this research output."
        )

    @staticmethod
    def _match_agent(name: str, table: Mapping[str, object]) -> str | None:
        """Return canonical agent when a whole-token/whole-alias matches."""
        tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
        for agent in sorted(table, key=len, reverse=True):
            agent_l = agent.lower()
            if "-" in agent_l:
                parts = agent_l.split("-")
                if all(part in tokens for part in parts):
                    return agent
            elif agent_l in tokens:
                return agent
        return None
