"""DOAC + NSAID bleeding intensifier safety checker.

Direct oral anticoagulants (DOACs) combined with NSAIDs increase major bleeding
risk through anticoagulation plus GI mucosal injury and platelet dysfunction.
This hazard is distinct from DOAC + antiplatelet screening, warfarin + NSAID
intensifier controls, and NSAID + SSRI/SNRI bleeding checks.

This checker flags DOAC agents (apixaban, rivaroxaban, edoxaban, dabigatran)
co-prescribed with NSAID partners (ibuprofen, naproxen, diclofenac, ketorolac,
meloxicam, celecoxib). Whole-token matching is used throughout. Findings are
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DoacNsaidRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_DOAC_AGENTS: Final[dict[str, str]] = {
    "apixaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "rivaroxaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "edoxaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "dabigatran": "a direct oral anticoagulant (direct thrombin inhibitor)",
}

_NSAID_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ibuprofen": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "naproxen": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "diclofenac": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "ketorolac": (
        "a potent NSAID with high GI bleeding risk",
        Severity.CRITICAL,
    ),
    "meloxicam": ("a nonsteroidal anti-inflammatory drug", Severity.HIGH),
    "celecoxib": ("a COX-2 selective NSAID", Severity.HIGH),
}


class DoacNsaidChecker:
    """Flag DOACs co-prescribed with NSAID bleed intensifiers."""

    def check(self, medications: list[Medication]) -> list[DoacNsaidRisk]:
        """Return one finding per unique DOAC × NSAID pair."""
        doac_matches: list[tuple[int, Medication, str]] = []
        nsaid_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            doac_candidates = sorted(tokens & set(_DOAC_AGENTS))
            if doac_candidates:
                doac_matches.append((index, medication, doac_candidates[0]))

            nsaid_candidates = sorted(tokens & set(_NSAID_AGENTS))
            if nsaid_candidates:
                nsaid_matches.append((index, medication, nsaid_candidates[0]))

        if not doac_matches or not nsaid_matches:
            logger.info("doac_nsaid_checked", findings=0)
            return []

        doac_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        nsaid_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[DoacNsaidRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for doac_index, doac_med, doac_agent in doac_matches:
            for nsaid_index, nsaid_med, nsaid_agent in nsaid_matches:
                if doac_index == nsaid_index:
                    continue
                pair_key = (doac_agent, nsaid_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                nsaid_desc, severity = _NSAID_AGENTS[nsaid_agent]
                findings.append(
                    DoacNsaidRisk(
                        medication=doac_med.name,
                        agent=doac_agent,
                        partner_medication=nsaid_med.name,
                        partner_agent=nsaid_agent,
                        severity=severity,
                        rationale=self._build_rationale(
                            doac_medication=doac_med.name,
                            doac_agent=doac_agent,
                            doac_descriptor=_DOAC_AGENTS[doac_agent],
                            nsaid_medication=nsaid_med.name,
                            nsaid_agent=nsaid_agent,
                            nsaid_descriptor=nsaid_desc,
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
            "doac_nsaid_checked",
            findings=len(findings),
            doac_agents=len({agent for _index, _medication, agent in doac_matches}),
            nsaid_agents=len({agent for _index, _medication, agent in nsaid_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        doac_medication: str,
        doac_agent: str,
        doac_descriptor: str,
        nsaid_medication: str,
        nsaid_agent: str,
        nsaid_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY DOAC × NSAID rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{doac_medication}' contains {doac_agent}, "
            f"{doac_descriptor}, and is co-prescribed with '{nsaid_medication}' "
            f"({nsaid_agent}, {nsaid_descriptor}). Concurrent DOAC anticoagulation "
            "with an NSAID intensifies major bleeding risk via anticoagulation plus "
            "GI mucosal injury and platelet dysfunction. Review urgently; consider "
            "NSAID alternatives, gastroprotection, and closer bleeding-risk monitoring "
            "with a qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
