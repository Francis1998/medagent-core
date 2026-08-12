"""SSRI/SNRI + triptan serotonin-syndrome pair safety checker.

SSRIs and SNRIs increase serotonergic tone; triptan antimigraine agents also
agonize serotonin receptors. Concurrent use is a focused serotonin-syndrome
risk pair. This hazard is distinct from the broader multi-class serotonin
syndrome panel and from NSAID + SSRI/SNRI bleeding intensification.

Whole-token matching is used throughout. Findings are deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, SsriTriptanRisk

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
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

_TRIPTAN_AGENTS: Final[dict[str, str]] = {
    "sumatriptan": "a triptan antimigraine serotonin receptor agonist",
    "rizatriptan": "a triptan antimigraine serotonin receptor agonist",
    "eletriptan": "a triptan antimigraine serotonin receptor agonist",
    "zolmitriptan": "a triptan antimigraine serotonin receptor agonist",
    "naratriptan": "a triptan antimigraine serotonin receptor agonist",
    "almotriptan": "a triptan antimigraine serotonin receptor agonist",
    "frovatriptan": "a triptan antimigraine serotonin receptor agonist",
}


class SsriTriptanChecker:
    """Flag SSRI/SNRI antidepressants co-prescribed with triptan antimigraines."""

    def check(self, medications: list[Medication]) -> list[SsriTriptanRisk]:
        """Return one finding per unique SSRI/SNRI × triptan pair.

        Findings are ordered by descending severity, medication names, and
        canonical agents. An empty list is returned when either medication
        class is absent.
        """
        ssri_snri_matches: list[tuple[int, Medication, str]] = []
        triptan_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            ssri_snri_candidates = sorted(tokens & set(_SSRI_SNRI_AGENTS))
            if ssri_snri_candidates:
                ssri_snri_matches.append((index, medication, ssri_snri_candidates[0]))

            triptan_candidates = sorted(tokens & set(_TRIPTAN_AGENTS))
            if triptan_candidates:
                triptan_matches.append((index, medication, triptan_candidates[0]))

        if not ssri_snri_matches or not triptan_matches:
            logger.info("ssri_triptan_checked", findings=0)
            return []

        ssri_snri_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        triptan_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[SsriTriptanRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for ssri_snri_index, ssri_snri_med, ssri_snri_agent in ssri_snri_matches:
            antidepressant_class = _SSRI_SNRI_AGENTS[ssri_snri_agent]
            for triptan_index, triptan_med, triptan_agent in triptan_matches:
                if ssri_snri_index == triptan_index:
                    continue
                pair_key = (ssri_snri_agent, triptan_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                findings.append(
                    SsriTriptanRisk(
                        medication=ssri_snri_med.name,
                        agent=ssri_snri_agent,
                        partner_medication=triptan_med.name,
                        partner_agent=triptan_agent,
                        antidepressant_class=antidepressant_class,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            antidepressant_medication=ssri_snri_med.name,
                            antidepressant_agent=ssri_snri_agent,
                            antidepressant_class=antidepressant_class,
                            triptan_medication=triptan_med.name,
                            triptan_agent=triptan_agent,
                            triptan_descriptor=_TRIPTAN_AGENTS[triptan_agent],
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
            "ssri_triptan_checked",
            findings=len(findings),
            ssri_snri_agents=len({agent for _index, _medication, agent in ssri_snri_matches}),
            triptan_agents=len({agent for _index, _medication, agent in triptan_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        antidepressant_medication: str,
        antidepressant_agent: str,
        antidepressant_class: str,
        triptan_medication: str,
        triptan_agent: str,
        triptan_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY SSRI/SNRI × triptan rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{antidepressant_medication}' contains "
            f"{antidepressant_agent} ({antidepressant_class}), and is co-prescribed "
            f"with '{triptan_medication}' ({triptan_agent}, {triptan_descriptor}). "
            "Combining an SSRI/SNRI with a triptan increases serotonin-syndrome risk. "
            "Promptly review serotonergic co-therapy with a qualified clinician; "
            "do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
