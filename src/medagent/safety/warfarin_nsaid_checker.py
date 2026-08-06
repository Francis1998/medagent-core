"""Warfarin + NSAID bleeding intensifier safety checker.

Warfarin (and brand formulations Coumadin / Jantoven) combined with NSAIDs
increases major bleeding risk through anticoagulation plus GI mucosal injury
and platelet dysfunction. This hazard is distinct from the broader
anticoagulation bleeding-risk panel and generic drug-drug interaction
screening.

This checker flags warfarin-class anticoagulants co-prescribed with NSAID
partners (ibuprofen, naproxen, diclofenac, ketorolac, meloxicam, or aspirin).
It emits one finding per unique warfarin × NSAID agent pair across distinct
medication entries, uses whole-token matching (never loose substrings), and is
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, WarfarinNsaidRisk

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical warfarin-class anticoagulant token -> short descriptor.
_WARFARIN_AGENTS: Final[dict[str, str]] = {
    "warfarin": "a vitamin K antagonist anticoagulant",
    "coumadin": "a warfarin brand formulation (vitamin K antagonist)",
    "jantoven": "a warfarin brand formulation (vitamin K antagonist)",
}

# Canonical NSAID / aspirin token -> (descriptor, severity).
# Aspirin and parenteral-intensity NSAIDs (ketorolac) escalate to CRITICAL.
_NSAID_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ibuprofen": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "naproxen": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "diclofenac": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "ketorolac": (
        "a potent NSAID with high GI bleeding risk",
        Severity.CRITICAL,
    ),
    "meloxicam": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "aspirin": (
        "an antiplatelet / high-dose NSAID that intensifies anticoagulation bleeding",
        Severity.CRITICAL,
    ),
}


class WarfarinNsaidChecker:
    """Flag warfarin-class anticoagulants co-prescribed with NSAID bleed intensifiers."""

    def check(self, medications: list[Medication]) -> list[WarfarinNsaidRisk]:
        """Return findings for each warfarin × NSAID pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`WarfarinNsaidRisk` per unique warfarin × NSAID agent
            pair across distinct medication entries, ordered by descending
            severity then warfarin medication, partner medication, and agents.
            An empty list is returned when warfarin-class agents or NSAIDs
            are absent.
        """
        warfarin_matches: list[tuple[Medication, str]] = []
        nsaid_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            warfarin_candidates = sorted(tokens & set(_WARFARIN_AGENTS))
            if warfarin_candidates:
                warfarin_matches.append((medication, warfarin_candidates[0]))

            nsaid_candidates = sorted(tokens & set(_NSAID_AGENTS))
            if nsaid_candidates:
                nsaid_matches.append((medication, nsaid_candidates[0]))

        if not warfarin_matches or not nsaid_matches:
            logger.info("warfarin_nsaid_checked", findings=0)
            return []

        findings: list[WarfarinNsaidRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for warfarin_med, warfarin_agent in warfarin_matches:
            warfarin_desc = _WARFARIN_AGENTS[warfarin_agent]
            for nsaid_med, nsaid_agent in nsaid_matches:
                pair_key = (warfarin_agent, nsaid_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                nsaid_desc, severity = _NSAID_AGENTS[nsaid_agent]
                findings.append(
                    WarfarinNsaidRisk(
                        medication=warfarin_med.name,
                        agent=warfarin_agent,
                        partner_medication=nsaid_med.name,
                        partner_agent=nsaid_agent,
                        severity=severity,
                        rationale=self._build_rationale(
                            warfarin_medication=warfarin_med.name,
                            warfarin_agent=warfarin_agent,
                            warfarin_descriptor=warfarin_desc,
                            nsaid_medication=nsaid_med.name,
                            nsaid_agent=nsaid_agent,
                            nsaid_descriptor=nsaid_desc,
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
            "warfarin_nsaid_checked",
            findings=len(findings),
            warfarin_agents=len({agent for _med, agent in warfarin_matches}),
            nsaid_agents=len({agent for _med, agent in nsaid_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        warfarin_medication: str,
        warfarin_agent: str,
        warfarin_descriptor: str,
        nsaid_medication: str,
        nsaid_agent: str,
        nsaid_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY warfarin × NSAID rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{warfarin_medication}' contains {warfarin_agent}, "
            f"{warfarin_descriptor}, and is co-prescribed with '{nsaid_medication}' "
            f"({nsaid_agent}, {nsaid_descriptor}). Concurrent warfarin-class "
            "anticoagulation with an NSAID intensifies major bleeding risk via "
            "GI mucosal injury and platelet dysfunction. Review urgently; consider "
            "NSAID alternatives, gastroprotection, and closer INR monitoring."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
