"""Macrolide + digoxin P-glycoprotein interaction safety checker.

Clarithromycin and erythromycin inhibit P-glycoprotein (P-gp) and can raise
digoxin serum concentrations, increasing digoxin toxicity risk. Azithromycin is
a weaker P-gp inhibitor and is intentionally excluded from this panel. This
hazard is distinct from digoxin + amiodarone level monitoring and digoxin
toxicity electrolyte screening.

This checker flags digoxin (or lanoxin) co-prescribed with erythromycin or
clarithromycin. Whole-token matching is used throughout. Findings are
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import MacrolideDigoxinRisk, Medication, Severity

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

# Canonical P-gp-inhibiting macrolide token -> short descriptor.
# Azithromycin intentionally omitted (weaker P-gp inhibition).
_MACROLIDE_AGENTS: Final[dict[str, str]] = {
    "erythromycin": "a macrolide antibiotic that inhibits P-glycoprotein",
    "clarithromycin": "a macrolide antibiotic that inhibits P-glycoprotein",
}


class MacrolideDigoxinChecker:
    """Flag digoxin co-prescribed with P-gp-inhibiting macrolides."""

    def check(self, medications: list[Medication]) -> list[MacrolideDigoxinRisk]:
        """Return findings for each digoxin × macrolide pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`MacrolideDigoxinRisk` per unique digoxin × macrolide
            agent pair across distinct medication entries, ordered by descending
            severity then digoxin medication, partner medication, and agents.
            An empty list is returned when digoxin or panel macrolides are
            absent.
        """
        digoxin_matches: list[tuple[Medication, str]] = []
        macrolide_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            digoxin_candidates = sorted(tokens & set(_DIGOXIN_AGENTS))
            if digoxin_candidates:
                digoxin_matches.append((medication, digoxin_candidates[0]))

            macrolide_candidates = sorted(tokens & set(_MACROLIDE_AGENTS))
            if macrolide_candidates:
                macrolide_matches.append((medication, macrolide_candidates[0]))

        if not digoxin_matches or not macrolide_matches:
            logger.info("macrolide_digoxin_checked", findings=0)
            return []

        findings: list[MacrolideDigoxinRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for digoxin_med, digoxin_agent in digoxin_matches:
            digoxin_desc = _DIGOXIN_AGENTS[digoxin_agent]
            for macrolide_med, macrolide_agent in macrolide_matches:
                pair_key = (digoxin_agent, macrolide_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                macrolide_desc = _MACROLIDE_AGENTS[macrolide_agent]
                findings.append(
                    MacrolideDigoxinRisk(
                        medication=digoxin_med.name,
                        agent=digoxin_agent,
                        partner_medication=macrolide_med.name,
                        partner_agent=macrolide_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            digoxin_medication=digoxin_med.name,
                            digoxin_agent=digoxin_agent,
                            digoxin_descriptor=digoxin_desc,
                            macrolide_medication=macrolide_med.name,
                            macrolide_agent=macrolide_agent,
                            macrolide_descriptor=macrolide_desc,
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
            "macrolide_digoxin_checked",
            findings=len(findings),
            digoxin_agents=len({agent for _med, agent in digoxin_matches}),
            macrolide_agents=len({agent for _med, agent in macrolide_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        digoxin_medication: str,
        digoxin_agent: str,
        digoxin_descriptor: str,
        macrolide_medication: str,
        macrolide_agent: str,
        macrolide_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY digoxin × macrolide P-gp rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{digoxin_medication}' contains {digoxin_agent}, "
            f"{digoxin_descriptor}, and is co-prescribed with '{macrolide_medication}' "
            f"({macrolide_agent}, {macrolide_descriptor}). Clarithromycin and "
            "erythromycin inhibit P-glycoprotein and can raise digoxin serum "
            "concentrations, increasing digoxin toxicity risk. Review urgently; "
            "consider digoxin dose reduction, serum digoxin level monitoring, or "
            "an alternative antibiotic when clinically appropriate."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
