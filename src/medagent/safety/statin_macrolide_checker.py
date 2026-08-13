"""Statin + macrolide CYP3A4 interaction safety checker.

Simvastatin, lovastatin, and atorvastatin are metabolized by CYP3A4.
Clarithromycin and erythromycin are strong CYP3A4-inhibiting macrolides that
increase systemic statin exposure and myopathy / rhabdomyolysis risk. This
hazard is a focused macrolide pair distinct from the broader statin + strong
CYP3A4 inhibitor panel. Azithromycin is intentionally excluded.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, StatinMacrolideRisk

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_STATIN_AGENTS: Final[dict[str, str]] = {
    "simvastatin": "an HMG-CoA reductase inhibitor with high CYP3A4 dependence",
    "lovastatin": "an HMG-CoA reductase inhibitor with high CYP3A4 dependence",
    "atorvastatin": "an HMG-CoA reductase inhibitor metabolized by CYP3A4",
}

# Azithromycin intentionally omitted (weaker CYP3A4 inhibition).
_MACROLIDE_AGENTS: Final[dict[str, str]] = {
    "clarithromycin": "a macrolide antibiotic and strong CYP3A4 inhibitor",
    "erythromycin": "a macrolide antibiotic and strong CYP3A4 inhibitor",
}


class StatinMacrolideChecker:
    """Flag CYP3A4-metabolized statins co-prescribed with strong macrolides."""

    def check(self, medications: list[Medication]) -> list[StatinMacrolideRisk]:
        """Return one finding per unique statin × macrolide pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        statin_matches: list[tuple[int, Medication, str]] = []
        macrolide_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            statin_candidates = sorted(tokens & set(_STATIN_AGENTS))
            if statin_candidates:
                statin_matches.append((index, medication, statin_candidates[0]))

            macrolide_candidates = sorted(tokens & set(_MACROLIDE_AGENTS))
            if macrolide_candidates:
                macrolide_matches.append((index, medication, macrolide_candidates[0]))

        if not statin_matches or not macrolide_matches:
            logger.info("statin_macrolide_checked", findings=0)
            return []

        statin_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        macrolide_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[StatinMacrolideRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for statin_index, statin_med, statin_agent in statin_matches:
            for macrolide_index, macrolide_med, macrolide_agent in macrolide_matches:
                if statin_index == macrolide_index:
                    continue
                pair_key = (statin_agent, macrolide_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    StatinMacrolideRisk(
                        medication=statin_med.name,
                        agent=statin_agent,
                        partner_medication=macrolide_med.name,
                        partner_agent=macrolide_agent,
                        severity=self._severity_for(statin_agent),
                        rationale=self._build_rationale(
                            statin_medication=statin_med.name,
                            statin_agent=statin_agent,
                            statin_descriptor=_STATIN_AGENTS[statin_agent],
                            macrolide_medication=macrolide_med.name,
                            macrolide_agent=macrolide_agent,
                            macrolide_descriptor=_MACROLIDE_AGENTS[macrolide_agent],
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
            "statin_macrolide_checked",
            findings=len(findings),
            statin_agents=len({agent for _index, _medication, agent in statin_matches}),
            macrolide_agents=len({agent for _index, _medication, agent in macrolide_matches}),
        )
        return findings

    @staticmethod
    def _severity_for(statin_agent: str) -> Severity:
        """Map statin agent to advisory severity."""
        if statin_agent in {"simvastatin", "lovastatin"}:
            return Severity.CRITICAL
        return Severity.HIGH

    @staticmethod
    def _build_rationale(
        *,
        statin_medication: str,
        statin_agent: str,
        statin_descriptor: str,
        macrolide_medication: str,
        macrolide_agent: str,
        macrolide_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY statin × macrolide rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{statin_medication}' contains {statin_agent}, "
            f"{statin_descriptor}, and is co-prescribed with '{macrolide_medication}' "
            f"({macrolide_agent}, {macrolide_descriptor}). Strong CYP3A4-inhibiting "
            "macrolides markedly increase systemic statin exposure and the risk of "
            "myopathy and rhabdomyolysis. Promptly review statin therapy with a "
            "qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
