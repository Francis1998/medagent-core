"""Fluoroquinolone + NSAID CNS stimulation / seizure-risk safety checker.

Fluoroquinolone antibiotics lower the seizure threshold and can cause CNS
stimulation; concurrent NSAID use further intensifies that CNS risk. This
hazard is distinct from fluoroquinolone + warfarin INR potentiation and
warfarin + NSAID bleeding intensification.

This checker flags ciprofloxacin, levofloxacin, moxifloxacin, or ofloxacin
co-prescribed with NSAID partners. Whole-token matching is used throughout.
Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import FluoroquinoloneNsaidRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_FLUOROQUINOLONE_AGENTS: Final[dict[str, str]] = {
    "ciprofloxacin": "a fluoroquinolone antibiotic associated with CNS stimulation",
    "levofloxacin": "a fluoroquinolone antibiotic associated with CNS stimulation",
    "moxifloxacin": "a fluoroquinolone antibiotic associated with CNS stimulation",
    "ofloxacin": "a fluoroquinolone antibiotic associated with CNS stimulation",
}

_NSAID_AGENTS: Final[dict[str, str]] = {
    "ibuprofen": "a nonsteroidal anti-inflammatory drug",
    "naproxen": "a nonsteroidal anti-inflammatory drug",
    "diclofenac": "a nonsteroidal anti-inflammatory drug",
    "ketorolac": "a potent nonsteroidal anti-inflammatory drug",
    "meloxicam": "a nonsteroidal anti-inflammatory drug",
    "celecoxib": "a COX-2-selective nonsteroidal anti-inflammatory drug",
    "indomethacin": "a nonsteroidal anti-inflammatory drug",
    "piroxicam": "a nonsteroidal anti-inflammatory drug",
    "aspirin": "an NSAID with antiplatelet activity",
}


class FluoroquinoloneNsaidChecker:
    """Flag fluoroquinolones co-prescribed with NSAID CNS-risk intensifiers."""

    def check(self, medications: list[Medication]) -> list[FluoroquinoloneNsaidRisk]:
        """Return one finding per unique fluoroquinolone × NSAID pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        fluoroquinolone_matches: list[tuple[int, Medication, str]] = []
        nsaid_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            fluoroquinolone_candidates = sorted(tokens & set(_FLUOROQUINOLONE_AGENTS))
            if fluoroquinolone_candidates:
                fluoroquinolone_matches.append((index, medication, fluoroquinolone_candidates[0]))

            nsaid_candidates = sorted(tokens & set(_NSAID_AGENTS))
            if nsaid_candidates:
                nsaid_matches.append((index, medication, nsaid_candidates[0]))

        if not fluoroquinolone_matches or not nsaid_matches:
            logger.info("fluoroquinolone_nsaid_checked", findings=0)
            return []

        fluoroquinolone_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        nsaid_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[FluoroquinoloneNsaidRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for (
            fluoroquinolone_index,
            fluoroquinolone_med,
            fluoroquinolone_agent,
        ) in fluoroquinolone_matches:
            fluoroquinolone_desc = _FLUOROQUINOLONE_AGENTS[fluoroquinolone_agent]
            for nsaid_index, nsaid_med, nsaid_agent in nsaid_matches:
                if fluoroquinolone_index == nsaid_index:
                    continue
                pair_key = (fluoroquinolone_agent, nsaid_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    FluoroquinoloneNsaidRisk(
                        medication=fluoroquinolone_med.name,
                        agent=fluoroquinolone_agent,
                        partner_medication=nsaid_med.name,
                        partner_agent=nsaid_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            fluoroquinolone_medication=fluoroquinolone_med.name,
                            fluoroquinolone_agent=fluoroquinolone_agent,
                            fluoroquinolone_descriptor=fluoroquinolone_desc,
                            nsaid_medication=nsaid_med.name,
                            nsaid_agent=nsaid_agent,
                            nsaid_descriptor=_NSAID_AGENTS[nsaid_agent],
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
            "fluoroquinolone_nsaid_checked",
            findings=len(findings),
            fluoroquinolone_agents=len(
                {agent for _index, _medication, agent in fluoroquinolone_matches}
            ),
            nsaid_agents=len({agent for _index, _medication, agent in nsaid_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        fluoroquinolone_medication: str,
        fluoroquinolone_agent: str,
        fluoroquinolone_descriptor: str,
        nsaid_medication: str,
        nsaid_agent: str,
        nsaid_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY fluoroquinolone × NSAID CNS rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{fluoroquinolone_medication}' contains "
            f"{fluoroquinolone_agent}, {fluoroquinolone_descriptor}, and is "
            f"co-prescribed with '{nsaid_medication}' ({nsaid_agent}, "
            f"{nsaid_descriptor}). Fluoroquinolones can lower the seizure "
            "threshold and cause CNS stimulation; concurrent NSAID use intensifies "
            "that CNS / seizure risk. Promptly review the combination with a "
            "qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
