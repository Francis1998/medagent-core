"""Statin + strong CYP3A4 inhibitor safety checker.

Simvastatin, lovastatin, and atorvastatin are metabolized primarily by CYP3A4.
Co-administration with strong CYP3A4 inhibitors increases systemic statin
exposure and the risk of myopathy and rhabdomyolysis. This hazard is distinct
from generic drug-drug interaction screening and drug-food grapefruit flagging.

This checker focuses on a conservative panel of statin × strong CYP3A4 inhibitor
combinations. It emits one finding per unique canonical pair across distinct
medication entries, uses whole-token matching (never loose substrings), and is
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, StatinCyp3a4Risk

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical statin token -> short descriptor.
_STATIN_AGENTS: Final[dict[str, str]] = {
    "simvastatin": "an HMG-CoA reductase inhibitor with high CYP3A4 dependence",
    "lovastatin": "an HMG-CoA reductase inhibitor with high CYP3A4 dependence",
    "atorvastatin": "an HMG-CoA reductase inhibitor metabolized by CYP3A4",
}

# Canonical strong CYP3A4 inhibitor token -> short descriptor.
_CYP3A4_INHIBITORS: Final[dict[str, str]] = {
    "clarithromycin": "a macrolide antibiotic and strong CYP3A4 inhibitor",
    "itraconazole": "an azole antifungal and strong CYP3A4 inhibitor",
    "ketoconazole": "an azole antifungal and strong CYP3A4 inhibitor",
    "ritonavir": "an HIV protease inhibitor and strong CYP3A4 inhibitor",
    "grapefruit": "a dietary CYP3A4 inhibitor (grapefruit juice exposure)",
}


class StatinCyp3a4Checker:
    """Flag statin co-prescription with strong CYP3A4 inhibitors."""

    def check(self, medications: list[Medication]) -> list[StatinCyp3a4Risk]:
        """Return findings for each statin × strong CYP3A4 inhibitor pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`StatinCyp3a4Risk` per unique statin × inhibitor pair
            across distinct medication entries, ordered by descending severity
            then statin medication, partner medication, and agents. An empty
            list is returned when no statin or no inhibitor partner is present.
        """
        statin_matches: list[tuple[Medication, str]] = []
        inhibitor_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            statin_candidates = sorted(tokens & set(_STATIN_AGENTS))
            if statin_candidates:
                statin_matches.append((medication, statin_candidates[0]))

            inhibitor_candidates = sorted(tokens & set(_CYP3A4_INHIBITORS))
            if inhibitor_candidates:
                inhibitor_matches.append((medication, inhibitor_candidates[0]))

        if not statin_matches or not inhibitor_matches:
            logger.info("statin_cyp3a4_checked", findings=0)
            return []

        distinct_statins = {agent for _med, agent in statin_matches}
        distinct_inhibitors = {agent for _med, agent in inhibitor_matches}
        if not distinct_statins or not distinct_inhibitors:
            logger.info("statin_cyp3a4_checked", findings=0)
            return []

        findings: list[StatinCyp3a4Risk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for statin_med, statin_agent in statin_matches:
            statin_desc = _STATIN_AGENTS[statin_agent]
            for inhibitor_med, inhibitor_agent in inhibitor_matches:
                pair_key = (statin_agent, inhibitor_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                inhibitor_desc = _CYP3A4_INHIBITORS[inhibitor_agent]
                findings.append(
                    StatinCyp3a4Risk(
                        medication=statin_med.name,
                        agent=statin_agent,
                        partner_medication=inhibitor_med.name,
                        partner_agent=inhibitor_agent,
                        severity=self._severity_for(statin_agent),
                        rationale=self._build_rationale(
                            statin_medication=statin_med.name,
                            statin_agent=statin_agent,
                            statin_descriptor=statin_desc,
                            inhibitor_medication=inhibitor_med.name,
                            inhibitor_agent=inhibitor_agent,
                            inhibitor_descriptor=inhibitor_desc,
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
            "statin_cyp3a4_checked",
            findings=len(findings),
            statin_agents=len(distinct_statins),
            inhibitor_agents=len(distinct_inhibitors),
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
        inhibitor_medication: str,
        inhibitor_agent: str,
        inhibitor_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY statin × CYP3A4 inhibitor rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{statin_medication}' contains {statin_agent}, {statin_descriptor}, "
            f"and is co-prescribed with '{inhibitor_medication}' ({inhibitor_agent}, "
            f"{inhibitor_descriptor}). Strong CYP3A4 inhibition markedly increases "
            "systemic statin exposure and the risk of myopathy and rhabdomyolysis. "
            "Review urgently and consider statin dose reduction, substitution, or "
            "discontinuation of the interacting agent."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
