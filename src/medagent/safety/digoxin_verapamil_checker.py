"""Digoxin + verapamil toxicity safety checker.

Verapamil inhibits P-glycoprotein and reduces digoxin clearance, raising digoxin
serum concentrations and toxicity risk. This hazard is distinct from digoxin +
amiodarone level monitoring and macrolide + digoxin P-gp interaction screening.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DigoxinVerapamilRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_DIGOXIN_AGENTS: Final[dict[str, str]] = {
    "digoxin": "a cardiac glycoside with a narrow therapeutic index",
    "lanoxin": "a digoxin brand formulation with a narrow therapeutic index",
}

_VERAPAMIL_AGENTS: Final[dict[str, str]] = {
    "verapamil": "a nondihydropyridine calcium-channel blocker that inhibits digoxin clearance",
    "calan": "a verapamil brand formulation that inhibits digoxin clearance",
    "isoptin": "a verapamil brand formulation that inhibits digoxin clearance",
    "verelan": "a verapamil brand formulation that inhibits digoxin clearance",
}


class DigoxinVerapamilChecker:
    """Flag digoxin co-prescribed with verapamil (P-gp / reduced clearance)."""

    def check(self, medications: list[Medication]) -> list[DigoxinVerapamilRisk]:
        """Return one finding per unique digoxin × verapamil pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        digoxin_matches: list[tuple[int, Medication, str]] = []
        verapamil_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            digoxin_candidates = sorted(tokens & set(_DIGOXIN_AGENTS))
            if digoxin_candidates:
                digoxin_matches.append((index, medication, digoxin_candidates[0]))

            verapamil_candidates = sorted(tokens & set(_VERAPAMIL_AGENTS))
            if verapamil_candidates:
                verapamil_matches.append((index, medication, verapamil_candidates[0]))

        if not digoxin_matches or not verapamil_matches:
            logger.info("digoxin_verapamil_checked", findings=0)
            return []

        digoxin_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        verapamil_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[DigoxinVerapamilRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for digoxin_index, digoxin_med, digoxin_agent in digoxin_matches:
            for verapamil_index, verapamil_med, verapamil_agent in verapamil_matches:
                if digoxin_index == verapamil_index:
                    continue
                pair_key = (digoxin_agent, verapamil_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    DigoxinVerapamilRisk(
                        medication=digoxin_med.name,
                        agent=digoxin_agent,
                        partner_medication=verapamil_med.name,
                        partner_agent=verapamil_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            digoxin_medication=digoxin_med.name,
                            digoxin_agent=digoxin_agent,
                            digoxin_descriptor=_DIGOXIN_AGENTS[digoxin_agent],
                            verapamil_medication=verapamil_med.name,
                            verapamil_agent=verapamil_agent,
                            verapamil_descriptor=_VERAPAMIL_AGENTS[verapamil_agent],
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
            "digoxin_verapamil_checked",
            findings=len(findings),
            digoxin_agents=len({agent for _index, _medication, agent in digoxin_matches}),
            verapamil_agents=len({agent for _index, _medication, agent in verapamil_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        digoxin_medication: str,
        digoxin_agent: str,
        digoxin_descriptor: str,
        verapamil_medication: str,
        verapamil_agent: str,
        verapamil_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY digoxin × verapamil rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{digoxin_medication}' contains {digoxin_agent}, "
            f"{digoxin_descriptor}, and is co-prescribed with '{verapamil_medication}' "
            f"({verapamil_agent}, {verapamil_descriptor}). Verapamil inhibits "
            "P-glycoprotein and reduces digoxin clearance, increasing digoxin toxicity "
            "risk. Promptly review digoxin dose and serum levels with a qualified "
            "clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
