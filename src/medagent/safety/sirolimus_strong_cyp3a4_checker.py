"""Sirolimus + Strong CYP3A4 Inhibitor Risk.

Sirolimus is a CYP3A4/P-gp substrate; strong CYP3A4 inhibitors raise
sirolimus levels and toxicity risk.
Distinct from tacrolimus CYP3A4 inhibitor exposure and other mTOR/CYP3A4 screens.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, SirolimusStrongCyp3a4Risk

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "sirolimus": "an mTOR inhibitor immunosuppressant CYP3A4/P-gp substrate",
    "rapamune": "a sirolimus brand mTOR inhibitor",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ketoconazole": (
        "a strong CYP3A4-inhibiting azole antifungal",
        Severity.CRITICAL,
    ),
    "clarithromycin": (
        "a strong CYP3A4-inhibiting macrolide antibiotic",
        Severity.CRITICAL,
    ),
    "itraconazole": (
        "a strong CYP3A4-inhibiting azole antifungal",
        Severity.CRITICAL,
    ),
    "ritonavir": (
        "a strong CYP3A4-inhibiting protease inhibitor / booster",
        Severity.CRITICAL,
    ),
    "grapefruit": (
        "a dietary strong CYP3A4 inhibitor cue",
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


class SirolimusStrongCyp3a4Checker:
    """Flag Sirolimus + Strong CYP3A4 Inhibitor Risk pairs."""

    def check(self, medications: list[Medication]) -> list[SirolimusStrongCyp3a4Risk]:
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
            logger.info("sirolimus_strong_cyp3a4_checker_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[SirolimusStrongCyp3a4Risk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    SirolimusStrongCyp3a4Risk(
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
        logger.info("sirolimus_strong_cyp3a4_checker_checked", findings=len(findings))
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
            "Sirolimus is a CYP3A4/P-gp substrate; strong CYP3A4 inhibitors raise "
            "sirolimus levels and toxicity risk. "
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
