"""Digoxin + amiodarone level-monitoring safety checker.

Amiodarone inhibits P-glycoprotein and reduces digoxin clearance, roughly
doubling digoxin serum concentrations. Co-prescription requires digoxin dose
reduction and serum digoxin level monitoring to avoid toxicity. This hazard is
distinct from digoxin toxicity electrolyte screening and generic drug-drug
interaction flagging.

This checker flags digoxin (or lanoxin) co-prescribed with amiodarone (or
cordarone), recommending digoxin level monitoring. It emits one finding per
unique digoxin × amiodarone agent pair across distinct medication entries, uses
whole-token matching (never loose substrings), and is deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DigoxinAmioRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical digoxin token -> short descriptor.
_DIGOXIN_AGENTS: Final[dict[str, str]] = {
    "digoxin": "a cardiac glycoside with a narrow therapeutic index",
    "lanoxin": "a digoxin brand formulation with a narrow therapeutic index",
}

# Canonical amiodarone token -> short descriptor.
_AMIODARONE_AGENTS: Final[dict[str, str]] = {
    "amiodarone": "a class III antiarrhythmic that inhibits digoxin clearance",
    "cordarone": "an amiodarone brand formulation that inhibits digoxin clearance",
}


class DigoxinAmioChecker:
    """Flag digoxin co-prescribed with amiodarone and recommend level monitoring."""

    def check(self, medications: list[Medication]) -> list[DigoxinAmioRisk]:
        """Return findings for each digoxin × amiodarone pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`DigoxinAmioRisk` per unique digoxin × amiodarone agent
            pair across distinct medication entries, ordered by descending
            severity then digoxin medication, partner medication, and agents.
            An empty list is returned when digoxin or amiodarone is absent.
        """
        digoxin_matches: list[tuple[Medication, str]] = []
        amio_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            digoxin_candidates = sorted(tokens & set(_DIGOXIN_AGENTS))
            if digoxin_candidates:
                digoxin_matches.append((medication, digoxin_candidates[0]))

            amio_candidates = sorted(tokens & set(_AMIODARONE_AGENTS))
            if amio_candidates:
                amio_matches.append((medication, amio_candidates[0]))

        if not digoxin_matches or not amio_matches:
            logger.info("digoxin_amio_checked", findings=0)
            return []

        findings: list[DigoxinAmioRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for digoxin_med, digoxin_agent in digoxin_matches:
            digoxin_desc = _DIGOXIN_AGENTS[digoxin_agent]
            for amio_med, amio_agent in amio_matches:
                pair_key = (digoxin_agent, amio_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                amio_desc = _AMIODARONE_AGENTS[amio_agent]
                findings.append(
                    DigoxinAmioRisk(
                        medication=digoxin_med.name,
                        agent=digoxin_agent,
                        partner_medication=amio_med.name,
                        partner_agent=amio_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            digoxin_medication=digoxin_med.name,
                            digoxin_agent=digoxin_agent,
                            digoxin_descriptor=digoxin_desc,
                            amio_medication=amio_med.name,
                            amio_agent=amio_agent,
                            amio_descriptor=amio_desc,
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
            "digoxin_amio_checked",
            findings=len(findings),
            digoxin_agents=len({agent for _med, agent in digoxin_matches}),
            amio_agents=len({agent for _med, agent in amio_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        digoxin_medication: str,
        digoxin_agent: str,
        digoxin_descriptor: str,
        amio_medication: str,
        amio_agent: str,
        amio_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY digoxin × amiodarone rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{digoxin_medication}' contains {digoxin_agent}, "
            f"{digoxin_descriptor}, and is co-prescribed with '{amio_medication}' "
            f"({amio_agent}, {amio_descriptor}). Amiodarone inhibits digoxin clearance "
            "and can approximately double digoxin serum concentrations. Reduce digoxin "
            "dose as indicated and obtain serum digoxin level monitoring to avoid "
            "toxicity."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
