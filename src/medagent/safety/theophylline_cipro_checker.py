"""Theophylline + strong CYP1A2-inhibiting quinolone safety checker.

Ciprofloxacin and enoxacin inhibit CYP1A2-mediated theophylline metabolism,
raising serum theophylline concentrations and toxicity risk. Enoxacin is
treated as the stronger interaction. Other fluoroquinolones are outside this
focused panel.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, TheophyllineCiproRisk

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_THEOPHYLLINE_AGENTS: Final[dict[str, str]] = {
    "theophylline": "a methylxanthine with a narrow therapeutic index",
    "aminophylline": "a theophylline formulation with a narrow therapeutic index",
    "uniphyl": "a theophylline brand formulation with a narrow therapeutic index",
    "theochron": "a theophylline brand formulation with a narrow therapeutic index",
}

_QUINOLONE_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ciprofloxacin": (
        "a quinolone antibiotic and clinically important CYP1A2 inhibitor",
        Severity.HIGH,
    ),
    "cipro": (
        "a ciprofloxacin brand and clinically important CYP1A2 inhibitor",
        Severity.HIGH,
    ),
    "enoxacin": ("a quinolone antibiotic and potent CYP1A2 inhibitor", Severity.CRITICAL),
}


class TheophyllineCiproChecker:
    """Flag theophylline co-prescribed with focused CYP1A2-inhibiting quinolones."""

    def check(self, medications: list[Medication]) -> list[TheophyllineCiproRisk]:
        """Return one finding per unique theophylline × quinolone pair."""
        theophylline_matches: list[tuple[int, Medication, str]] = []
        quinolone_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            theophylline_candidates = sorted(tokens & set(_THEOPHYLLINE_AGENTS))
            if theophylline_candidates:
                theophylline_matches.append((index, medication, theophylline_candidates[0]))

            quinolone_candidates = sorted(tokens & set(_QUINOLONE_AGENTS))
            if quinolone_candidates:
                quinolone_matches.append((index, medication, quinolone_candidates[0]))

        if not theophylline_matches or not quinolone_matches:
            logger.info("theophylline_cipro_checked", findings=0)
            return []

        theophylline_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        quinolone_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[TheophyllineCiproRisk] = []
        seen: set[tuple[str, str]] = set()

        for theophylline_index, theophylline_med, theophylline_agent in theophylline_matches:
            for quinolone_index, quinolone_med, quinolone_agent in quinolone_matches:
                pair_key = (theophylline_agent, quinolone_agent)
                if theophylline_index == quinolone_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                quinolone_descriptor, severity = _QUINOLONE_AGENTS[quinolone_agent]
                findings.append(
                    TheophyllineCiproRisk(
                        medication=theophylline_med.name,
                        agent=theophylline_agent,
                        partner_medication=quinolone_med.name,
                        partner_agent=quinolone_agent,
                        severity=severity,
                        rationale=self._build_rationale(
                            theophylline_medication=theophylline_med.name,
                            theophylline_agent=theophylline_agent,
                            quinolone_medication=quinolone_med.name,
                            quinolone_agent=quinolone_agent,
                            quinolone_descriptor=quinolone_descriptor,
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
        logger.info("theophylline_cipro_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        theophylline_medication: str,
        theophylline_agent: str,
        quinolone_medication: str,
        quinolone_agent: str,
        quinolone_descriptor: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{theophylline_medication}' contains {theophylline_agent}, "
            f"{_THEOPHYLLINE_AGENTS[theophylline_agent]}, and is co-prescribed with "
            f"'{quinolone_medication}' ({quinolone_agent}, {quinolone_descriptor}). "
            "CYP1A2 inhibition may reduce theophylline clearance, raise serum "
            "concentrations, and cause nausea, tremor, seizures, or serious arrhythmias. "
            "Promptly review alternatives, theophylline dose, and serum-level monitoring "
            "with a qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
