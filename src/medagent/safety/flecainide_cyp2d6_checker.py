"""Flecainide + Strong CYP2D6 Inhibitor Risk.

Flecainide is a CYP2D6 substrate; strong CYP2D6 inhibitors raise
flecainide levels and proarrhythmia risk.
Distinct from related CYP/bleeding checkers covering other pairs.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import FlecainideCyp2d6Risk, Medication, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "flecainide": "a class Ic antiarrhythmic CYP2D6 substrate",
    "tambocor": "a flecainide brand class Ic antiarrhythmic",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "fluoxetine": (
        "a strong CYP2D6 inhibitor SSRI",
        Severity.HIGH,
    ),
    "paroxetine": (
        "a strong CYP2D6 inhibitor SSRI",
        Severity.HIGH,
    ),
    "bupropion": (
        "a strong CYP2D6 inhibitor antidepressant",
        Severity.HIGH,
    ),
    "quinidine": (
        "a strong CYP2D6 inhibitor antiarrhythmic",
        Severity.HIGH,
    ),
    "prozac": (
        "a fluoxetine brand strong CYP2D6 inhibitor",
        Severity.HIGH,
    ),
    "paxil": (
        "a paroxetine brand strong CYP2D6 inhibitor",
        Severity.HIGH,
    ),
}

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class FlecainideCyp2d6Checker:
    """Flag Flecainide + Strong CYP2D6 Inhibitor Risk pairs."""

    def check(self, medications: list[Medication]) -> list[FlecainideCyp2d6Risk]:
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
            logger.info("flecainide_cyp2d6_checker_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[FlecainideCyp2d6Risk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    FlecainideCyp2d6Risk(
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
        logger.info("flecainide_cyp2d6_checker_checked", findings=len(findings))
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
            "Flecainide is a CYP2D6 substrate; strong CYP2D6 inhibitors raise "
            "flecainide levels and proarrhythmia risk. "
            "Promptly review with a qualified clinician; do not change therapy "
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
