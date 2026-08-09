"""Amiodarone + warfarin INR interaction safety checker.

Amiodarone inhibits warfarin metabolism and can raise INR, increasing bleeding
risk. This hazard is distinct from digoxin + amiodarone level monitoring,
warfarin + NSAID bleed intensifier screening, and generic drug-drug interaction
flagging.

This checker flags amiodarone-class agents (amiodarone, cordarone, pacerone)
co-prescribed with warfarin-class anticoagulants (warfarin, coumadin,
jantoven). Whole-token matching is used throughout. Findings are deterministic
and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AmioWarfarinRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical amiodarone-class token -> short descriptor.
_AMIODARONE_AGENTS: Final[dict[str, str]] = {
    "amiodarone": "an antiarrhythmic that inhibits warfarin metabolism",
    "cordarone": "an amiodarone brand formulation that inhibits warfarin metabolism",
    "pacerone": "an amiodarone brand formulation that inhibits warfarin metabolism",
}

# Canonical warfarin-class anticoagulant token -> short descriptor.
_WARFARIN_AGENTS: Final[dict[str, str]] = {
    "warfarin": "a vitamin K antagonist anticoagulant",
    "coumadin": "a warfarin brand formulation (vitamin K antagonist)",
    "jantoven": "a warfarin brand formulation (vitamin K antagonist)",
}


class AmioWarfarinChecker:
    """Flag amiodarone co-prescribed with warfarin (INR potentiation)."""

    def check(self, medications: list[Medication]) -> list[AmioWarfarinRisk]:
        """Return findings for each amiodarone × warfarin pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`AmioWarfarinRisk` per unique amiodarone × warfarin agent
            pair across distinct medication entries, ordered by descending
            severity then amiodarone medication, partner medication, and agents.
            An empty list is returned when amiodarone-class or warfarin-class
            agents are absent.
        """
        amio_matches: list[tuple[Medication, str]] = []
        warfarin_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            amio_candidates = sorted(tokens & set(_AMIODARONE_AGENTS))
            if amio_candidates:
                amio_matches.append((medication, amio_candidates[0]))

            warfarin_candidates = sorted(tokens & set(_WARFARIN_AGENTS))
            if warfarin_candidates:
                warfarin_matches.append((medication, warfarin_candidates[0]))

        if not amio_matches or not warfarin_matches:
            logger.info("amio_warfarin_checked", findings=0)
            return []

        findings: list[AmioWarfarinRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for amio_med, amio_agent in amio_matches:
            amio_desc = _AMIODARONE_AGENTS[amio_agent]
            for warfarin_med, warfarin_agent in warfarin_matches:
                pair_key = (amio_agent, warfarin_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                warfarin_desc = _WARFARIN_AGENTS[warfarin_agent]
                findings.append(
                    AmioWarfarinRisk(
                        medication=amio_med.name,
                        agent=amio_agent,
                        partner_medication=warfarin_med.name,
                        partner_agent=warfarin_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            amio_medication=amio_med.name,
                            amio_agent=amio_agent,
                            amio_descriptor=amio_desc,
                            warfarin_medication=warfarin_med.name,
                            warfarin_agent=warfarin_agent,
                            warfarin_descriptor=warfarin_desc,
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
            "amio_warfarin_checked",
            findings=len(findings),
            amio_agents=len({agent for _med, agent in amio_matches}),
            warfarin_agents=len({agent for _med, agent in warfarin_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        amio_medication: str,
        amio_agent: str,
        amio_descriptor: str,
        warfarin_medication: str,
        warfarin_agent: str,
        warfarin_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY amiodarone × warfarin INR rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{amio_medication}' contains {amio_agent}, "
            f"{amio_descriptor}, and is co-prescribed with '{warfarin_medication}' "
            f"({warfarin_agent}, {warfarin_descriptor}). Amiodarone potentiates "
            "warfarin anticoagulation and can raise INR, increasing bleeding risk. "
            "Review urgently; consider warfarin dose reduction and closer INR "
            "monitoring when clinically appropriate."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
