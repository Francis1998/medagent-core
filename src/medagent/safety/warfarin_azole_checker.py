"""Warfarin + systemic azole antifungal interaction safety checker.

Systemic azole antifungals can inhibit CYP2C9 and other CYP pathways involved
in warfarin metabolism, increasing INR and bleeding risk. Topical clotrimazole
is intentionally excluded from this focused panel.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, WarfarinAzoleRisk

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_WARFARIN_AGENTS: Final[dict[str, str]] = {
    "warfarin": "a vitamin K antagonist anticoagulant",
    "coumadin": "a warfarin brand formulation (vitamin K antagonist)",
}

# Topical clotrimazole intentionally omitted.
_AZOLE_AGENTS: Final[dict[str, str]] = {
    "fluconazole": "a systemic azole with clinically important CYP2C9 inhibition",
    "ketoconazole": "a systemic azole and strong CYP inhibitor",
    "itraconazole": "a systemic triazole and strong CYP inhibitor",
    "voriconazole": "a systemic triazole with clinically important CYP2C9 inhibition",
}


class WarfarinAzoleChecker:
    """Flag warfarin co-prescribed with systemic azole antifungals."""

    def check(self, medications: list[Medication]) -> list[WarfarinAzoleRisk]:
        """Return one finding per unique warfarin × systemic azole pair."""
        warfarin_matches: list[tuple[int, Medication, str]] = []
        azole_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            warfarin_candidates = sorted(tokens & set(_WARFARIN_AGENTS))
            if warfarin_candidates:
                warfarin_matches.append((index, medication, warfarin_candidates[0]))

            azole_candidates = sorted(tokens & set(_AZOLE_AGENTS))
            if azole_candidates:
                azole_matches.append((index, medication, azole_candidates[0]))

        if not warfarin_matches or not azole_matches:
            logger.info("warfarin_azole_checked", findings=0)
            return []

        warfarin_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        azole_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[WarfarinAzoleRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for warfarin_index, warfarin_med, warfarin_agent in warfarin_matches:
            for azole_index, azole_med, azole_agent in azole_matches:
                if warfarin_index == azole_index:
                    continue
                pair_key = (warfarin_agent, azole_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    WarfarinAzoleRisk(
                        medication=warfarin_med.name,
                        agent=warfarin_agent,
                        partner_medication=azole_med.name,
                        partner_agent=azole_agent,
                        severity=self._severity_for(azole_agent),
                        rationale=self._build_rationale(
                            warfarin_medication=warfarin_med.name,
                            warfarin_agent=warfarin_agent,
                            warfarin_descriptor=_WARFARIN_AGENTS[warfarin_agent],
                            azole_medication=azole_med.name,
                            azole_agent=azole_agent,
                            azole_descriptor=_AZOLE_AGENTS[azole_agent],
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
            "warfarin_azole_checked",
            findings=len(findings),
            warfarin_agents=len({agent for _index, _medication, agent in warfarin_matches}),
            azole_agents=len({agent for _index, _medication, agent in azole_matches}),
        )
        return findings

    @staticmethod
    def _severity_for(azole_agent: str) -> Severity:
        """Map azole partner to advisory severity."""
        if azole_agent in {"fluconazole", "voriconazole"}:
            return Severity.CRITICAL
        return Severity.HIGH

    @staticmethod
    def _build_rationale(
        *,
        warfarin_medication: str,
        warfarin_agent: str,
        warfarin_descriptor: str,
        azole_medication: str,
        azole_agent: str,
        azole_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY warfarin × azole rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{warfarin_medication}' contains {warfarin_agent}, "
            f"{warfarin_descriptor}, and is co-prescribed with '{azole_medication}' "
            f"({azole_agent}, {azole_descriptor}). Systemic azole inhibition of CYP2C9 "
            "and other warfarin-metabolizing CYP pathways can markedly elevate INR and "
            "bleeding risk. Promptly review therapy and arrange closer INR monitoring "
            "with a qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
