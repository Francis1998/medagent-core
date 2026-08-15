"""Clopidogrel + CYP2C19-inhibiting PPI reduced-activation safety checker.

Omeprazole and esomeprazole inhibit CYP2C19, reducing conversion of clopidogrel
to its active metabolite and potentially diminishing antiplatelet effect. This
focused hazard is distinct from DOAC + antiplatelet screening and generic PPI
taper planning controls.

This checker flags clopidogrel (and Plavix) co-prescribed with omeprazole or
esomeprazole (including Prilosec and Nexium brand tokens). Whole-token matching
is used throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import ClopidogrelPpiRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_CLOPIDOGREL_AGENTS: Final[dict[str, str]] = {
    "clopidogrel": "a P2Y12 inhibitor prodrug requiring CYP2C19 activation",
    "plavix": "a clopidogrel brand formulation",
}

_CYP2C19_PPI_AGENTS: Final[dict[str, str]] = {
    "omeprazole": "a proton-pump inhibitor and strong CYP2C19 inhibitor",
    "esomeprazole": "a proton-pump inhibitor and strong CYP2C19 inhibitor",
    "prilosec": "an omeprazole brand formulation",
    "nexium": "an esomeprazole brand formulation",
}


class ClopidogrelPpiChecker:
    """Flag clopidogrel co-prescribed with CYP2C19-inhibiting PPIs."""

    def check(self, medications: list[Medication]) -> list[ClopidogrelPpiRisk]:
        """Return one finding per unique clopidogrel × CYP2C19 PPI pair."""
        clopidogrel_matches: list[tuple[int, Medication, str]] = []
        ppi_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            clopidogrel_candidates = sorted(tokens & set(_CLOPIDOGREL_AGENTS))
            if clopidogrel_candidates:
                clopidogrel_matches.append((index, medication, clopidogrel_candidates[0]))

            ppi_candidates = sorted(tokens & set(_CYP2C19_PPI_AGENTS))
            if ppi_candidates:
                ppi_matches.append((index, medication, ppi_candidates[0]))

        if not clopidogrel_matches or not ppi_matches:
            logger.info("clopidogrel_ppi_checked", findings=0)
            return []

        clopidogrel_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        ppi_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[ClopidogrelPpiRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for clopidogrel_index, clopidogrel_med, clopidogrel_agent in clopidogrel_matches:
            for ppi_index, ppi_med, ppi_agent in ppi_matches:
                if clopidogrel_index == ppi_index:
                    continue
                pair_key = (clopidogrel_agent, ppi_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    ClopidogrelPpiRisk(
                        medication=clopidogrel_med.name,
                        agent=clopidogrel_agent,
                        partner_medication=ppi_med.name,
                        partner_agent=ppi_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            clopidogrel_medication=clopidogrel_med.name,
                            clopidogrel_agent=clopidogrel_agent,
                            clopidogrel_descriptor=_CLOPIDOGREL_AGENTS[clopidogrel_agent],
                            ppi_medication=ppi_med.name,
                            ppi_agent=ppi_agent,
                            ppi_descriptor=_CYP2C19_PPI_AGENTS[ppi_agent],
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
            "clopidogrel_ppi_checked",
            findings=len(findings),
            clopidogrel_agents=len({agent for _index, _medication, agent in clopidogrel_matches}),
            ppi_agents=len({agent for _index, _medication, agent in ppi_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        clopidogrel_medication: str,
        clopidogrel_agent: str,
        clopidogrel_descriptor: str,
        ppi_medication: str,
        ppi_agent: str,
        ppi_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY clopidogrel × CYP2C19 PPI rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{clopidogrel_medication}' contains {clopidogrel_agent}, "
            f"{clopidogrel_descriptor}, and is co-prescribed with '{ppi_medication}' "
            f"({ppi_agent}, {ppi_descriptor}). Omeprazole and esomeprazole inhibit "
            "CYP2C19, reducing conversion of clopidogrel to its active metabolite and "
            "potentially diminishing antiplatelet effect. Review urgently; consider a "
            "CYP2C19-compatible PPI alternative with a qualified clinician; do not "
            "change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
