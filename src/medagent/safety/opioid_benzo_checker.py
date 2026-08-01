"""Opioid + benzodiazepine/Z-drug CNS depression safety checker.

Co-prescribing opioids with benzodiazepines or Z-drug hypnotics increases the
risk of profound CNS and respiratory depression, overdose, and death. These
hazards are distinct from opioid MED (morphine-equivalent dose) summation,
taper-schedule advisory flagging, and generic drug-drug interaction screening.

This checker focuses on a conservative panel of opioid × benzodiazepine/Z-drug
combinations. It emits one finding per unique canonical pair across distinct
medication entries, uses whole-token matching (never loose substrings), and is
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, OpioidBenzoRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical opioid token -> short descriptor.
_OPIOID_AGENTS: Final[dict[str, str]] = {
    "oxycodone": "an opioid analgesic",
    "hydrocodone": "an opioid analgesic",
    "morphine": "an opioid analgesic",
    "fentanyl": "a potent synthetic opioid analgesic",
    "hydromorphone": "an opioid analgesic",
    "codeine": "an opioid analgesic",
    "tramadol": "a weak opioid analgesic",
    "methadone": "a long-acting opioid analgesic",
}

# Canonical benzodiazepine / Z-drug token -> (drug class, descriptor).
_BENZO_AGENTS: Final[dict[str, tuple[str, str]]] = {
    "alprazolam": ("benzodiazepine", "a benzodiazepine anxiolytic"),
    "lorazepam": ("benzodiazepine", "a benzodiazepine anxiolytic/sedative"),
    "diazepam": ("benzodiazepine", "a long-acting benzodiazepine"),
    "clonazepam": ("benzodiazepine", "a benzodiazepine anticonvulsant/anxiolytic"),
    "midazolam": ("benzodiazepine", "a short-acting benzodiazepine sedative"),
    "temazepam": ("benzodiazepine", "a benzodiazepine hypnotic"),
    "zolpidem": ("Z-drug", "a non-benzodiazepine hypnotic (Z-drug)"),
    "zopiclone": ("Z-drug", "a non-benzodiazepine hypnotic (Z-drug)"),
    "eszopiclone": ("Z-drug", "a non-benzodiazepine hypnotic (Z-drug)"),
}


class OpioidBenzoChecker:
    """Flag opioid co-prescription with benzodiazepines or Z-drugs."""

    def check(self, medications: list[Medication]) -> list[OpioidBenzoRisk]:
        """Return findings for each opioid × benzodiazepine/Z-drug pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`OpioidBenzoRisk` per unique opioid × benzodiazepine/Z-drug
            pair across distinct medication entries, ordered by descending severity
            then opioid medication, partner medication, and agents. An empty list
            is returned when no opioid or no benzodiazepine/Z-drug partner is
            present.
        """
        opioid_matches: list[tuple[Medication, str]] = []
        benzo_matches: list[tuple[Medication, str, str, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            opioid_candidates = sorted(tokens & set(_OPIOID_AGENTS))
            if opioid_candidates:
                opioid_matches.append((medication, opioid_candidates[0]))

            benzo_candidates = [
                (agent, *_BENZO_AGENTS[agent]) for agent in sorted(tokens & set(_BENZO_AGENTS))
            ]
            if benzo_candidates:
                agent, drug_class, descriptor = benzo_candidates[0]
                benzo_matches.append((medication, agent, drug_class, descriptor))

        if not opioid_matches or not benzo_matches:
            logger.info("opioid_benzo_checked", findings=0)
            return []

        distinct_opioids = {agent for _med, agent in opioid_matches}
        distinct_benzos = {agent for _med, agent, _class, _desc in benzo_matches}
        if not distinct_opioids or not distinct_benzos:
            logger.info("opioid_benzo_checked", findings=0)
            return []

        findings: list[OpioidBenzoRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for opioid_med, opioid_agent in opioid_matches:
            opioid_desc = _OPIOID_AGENTS[opioid_agent]
            for benzo_med, benzo_agent, benzo_class, benzo_desc in benzo_matches:
                pair_key = (opioid_agent, benzo_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    OpioidBenzoRisk(
                        medication=opioid_med.name,
                        agent=opioid_agent,
                        partner_medication=benzo_med.name,
                        partner_agent=benzo_agent,
                        partner_drug_class=benzo_class,
                        severity=Severity.CRITICAL,
                        rationale=self._build_rationale(
                            opioid_medication=opioid_med.name,
                            opioid_agent=opioid_agent,
                            opioid_descriptor=opioid_desc,
                            benzo_medication=benzo_med.name,
                            benzo_agent=benzo_agent,
                            benzo_descriptor=benzo_desc,
                            benzo_class=benzo_class,
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
            "opioid_benzo_checked",
            findings=len(findings),
            opioid_agents=len(distinct_opioids),
            benzo_agents=len(distinct_benzos),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        opioid_medication: str,
        opioid_agent: str,
        opioid_descriptor: str,
        benzo_medication: str,
        benzo_agent: str,
        benzo_descriptor: str,
        benzo_class: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY opioid × benzodiazepine rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{opioid_medication}' contains {opioid_agent}, {opioid_descriptor}, "
            f"and is co-prescribed with '{benzo_medication}' ({benzo_agent}, {benzo_descriptor}, "
            f"{benzo_class}). Opioid plus benzodiazepine/Z-drug combinations markedly increase "
            "the risk of profound CNS and respiratory depression, overdose, and death. "
            "Review urgently and consider tapering or discontinuing one or both agents."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
