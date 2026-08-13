"""Fluoroquinolone + corticosteroid tendon-risk safety checker.

Fluoroquinolone antibiotics are associated with tendinopathy and tendon rupture;
concurrent systemic corticosteroid therapy further intensifies that tendon risk.
This hazard is distinct from fluoroquinolone + NSAID CNS/seizure risk and
fluoroquinolone + warfarin INR potentiation.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import FluoroquinoloneCorticosteroidRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_FLUOROQUINOLONE_AGENTS: Final[dict[str, str]] = {
    "ciprofloxacin": "a fluoroquinolone antibiotic associated with tendinopathy",
    "levofloxacin": "a fluoroquinolone antibiotic associated with tendinopathy",
    "moxifloxacin": "a fluoroquinolone antibiotic associated with tendinopathy",
    "ofloxacin": "a fluoroquinolone antibiotic associated with tendinopathy",
}

_CORTICOSTEROID_AGENTS: Final[dict[str, str]] = {
    "prednisone": "a systemic corticosteroid that intensifies fluoroquinolone tendon risk",
    "prednisolone": "a systemic corticosteroid that intensifies fluoroquinolone tendon risk",
    "methylprednisolone": "a systemic corticosteroid that intensifies fluoroquinolone tendon risk",
    "dexamethasone": "a systemic corticosteroid that intensifies fluoroquinolone tendon risk",
    "hydrocortisone": "a systemic corticosteroid that intensifies fluoroquinolone tendon risk",
    "betamethasone": "a systemic corticosteroid that intensifies fluoroquinolone tendon risk",
}


class FluoroquinoloneCorticosteroidChecker:
    """Flag fluoroquinolones co-prescribed with systemic corticosteroids."""

    def check(self, medications: list[Medication]) -> list[FluoroquinoloneCorticosteroidRisk]:
        """Return one finding per unique fluoroquinolone × corticosteroid pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        fluoroquinolone_matches: list[tuple[int, Medication, str]] = []
        corticosteroid_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            fluoroquinolone_candidates = sorted(tokens & set(_FLUOROQUINOLONE_AGENTS))
            if fluoroquinolone_candidates:
                fluoroquinolone_matches.append((index, medication, fluoroquinolone_candidates[0]))

            corticosteroid_candidates = sorted(tokens & set(_CORTICOSTEROID_AGENTS))
            if corticosteroid_candidates:
                corticosteroid_matches.append((index, medication, corticosteroid_candidates[0]))

        if not fluoroquinolone_matches or not corticosteroid_matches:
            logger.info("fluoroquinolone_corticosteroid_checked", findings=0)
            return []

        fluoroquinolone_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        corticosteroid_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[FluoroquinoloneCorticosteroidRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for fq_index, fq_med, fq_agent in fluoroquinolone_matches:
            for steroid_index, steroid_med, steroid_agent in corticosteroid_matches:
                if fq_index == steroid_index:
                    continue
                pair_key = (fq_agent, steroid_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    FluoroquinoloneCorticosteroidRisk(
                        medication=fq_med.name,
                        agent=fq_agent,
                        partner_medication=steroid_med.name,
                        partner_agent=steroid_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            fluoroquinolone_medication=fq_med.name,
                            fluoroquinolone_agent=fq_agent,
                            fluoroquinolone_descriptor=_FLUOROQUINOLONE_AGENTS[fq_agent],
                            corticosteroid_medication=steroid_med.name,
                            corticosteroid_agent=steroid_agent,
                            corticosteroid_descriptor=_CORTICOSTEROID_AGENTS[steroid_agent],
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
            "fluoroquinolone_corticosteroid_checked",
            findings=len(findings),
            fluoroquinolone_agents=len(
                {agent for _index, _medication, agent in fluoroquinolone_matches}
            ),
            corticosteroid_agents=len(
                {agent for _index, _medication, agent in corticosteroid_matches}
            ),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        fluoroquinolone_medication: str,
        fluoroquinolone_agent: str,
        fluoroquinolone_descriptor: str,
        corticosteroid_medication: str,
        corticosteroid_agent: str,
        corticosteroid_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY fluoroquinolone × corticosteroid rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{fluoroquinolone_medication}' contains "
            f"{fluoroquinolone_agent}, {fluoroquinolone_descriptor}, and is co-prescribed "
            f"with '{corticosteroid_medication}' ({corticosteroid_agent}, "
            f"{corticosteroid_descriptor}). Combining a fluoroquinolone with a systemic "
            "corticosteroid increases tendon rupture and tendinopathy risk. Promptly "
            "review tendon symptoms and therapy with a qualified clinician; do not change "
            "therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
