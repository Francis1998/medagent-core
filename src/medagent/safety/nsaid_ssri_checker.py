"""NSAID + SSRI/SNRI bleeding-intensifier safety checker.

NSAIDs cause gastrointestinal mucosal injury and inhibit platelet function;
SSRIs and SNRIs can further impair platelet aggregation through serotonin
depletion. Concurrent use therefore increases gastrointestinal and other
bleeding risk. This hazard is distinct from warfarin + NSAID bleeding
intensification and tramadol + SSRI/SNRI seizure/serotonin risk.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, NsaidSsriBleedRisk, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
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

# Canonical antidepressant token -> drug class.
_SSRI_SNRI_AGENTS: Final[dict[str, str]] = {
    "sertraline": "SSRI",
    "fluoxetine": "SSRI",
    "paroxetine": "SSRI",
    "citalopram": "SSRI",
    "escitalopram": "SSRI",
    "fluvoxamine": "SSRI",
    "venlafaxine": "SNRI",
    "desvenlafaxine": "SNRI",
    "duloxetine": "SNRI",
    "levomilnacipran": "SNRI",
    "milnacipran": "SNRI",
}


class NsaidSsriBleedChecker:
    """Flag NSAIDs co-prescribed with SSRI/SNRI bleed intensifiers."""

    def check(self, medications: list[Medication]) -> list[NsaidSsriBleedRisk]:
        """Return one finding per unique NSAID × SSRI/SNRI pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        nsaid_matches: list[tuple[int, Medication, str]] = []
        ssri_snri_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            nsaid_candidates = sorted(tokens & set(_NSAID_AGENTS))
            if nsaid_candidates:
                nsaid_matches.append((index, medication, nsaid_candidates[0]))

            ssri_snri_candidates = sorted(tokens & set(_SSRI_SNRI_AGENTS))
            if ssri_snri_candidates:
                ssri_snri_matches.append((index, medication, ssri_snri_candidates[0]))

        if not nsaid_matches or not ssri_snri_matches:
            logger.info("nsaid_ssri_bleed_checked", findings=0)
            return []

        nsaid_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        ssri_snri_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[NsaidSsriBleedRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for nsaid_index, nsaid_med, nsaid_agent in nsaid_matches:
            for ssri_snri_index, ssri_snri_med, ssri_snri_agent in ssri_snri_matches:
                if nsaid_index == ssri_snri_index:
                    continue
                pair_key = (nsaid_agent, ssri_snri_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                partner_class = _SSRI_SNRI_AGENTS[ssri_snri_agent]
                findings.append(
                    NsaidSsriBleedRisk(
                        medication=nsaid_med.name,
                        agent=nsaid_agent,
                        partner_medication=ssri_snri_med.name,
                        partner_agent=ssri_snri_agent,
                        partner_drug_class=partner_class,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            nsaid_medication=nsaid_med.name,
                            nsaid_agent=nsaid_agent,
                            nsaid_descriptor=_NSAID_AGENTS[nsaid_agent],
                            antidepressant_medication=ssri_snri_med.name,
                            antidepressant_agent=ssri_snri_agent,
                            antidepressant_class=partner_class,
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
            "nsaid_ssri_bleed_checked",
            findings=len(findings),
            nsaid_agents=len({agent for _index, _medication, agent in nsaid_matches}),
            ssri_snri_agents=len({agent for _index, _medication, agent in ssri_snri_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        nsaid_medication: str,
        nsaid_agent: str,
        nsaid_descriptor: str,
        antidepressant_medication: str,
        antidepressant_agent: str,
        antidepressant_class: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY NSAID × SSRI/SNRI rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{nsaid_medication}' contains {nsaid_agent}, "
            f"{nsaid_descriptor}, and is co-prescribed with "
            f"'{antidepressant_medication}' ({antidepressant_agent}, "
            f"{antidepressant_class}). NSAID-related GI mucosal injury and platelet "
            "inhibition combined with SSRI/SNRI-related impairment of platelet "
            "aggregation increases gastrointestinal and other bleeding risk. "
            "Promptly review bleeding-risk mitigation with a qualified clinician; "
            "do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
