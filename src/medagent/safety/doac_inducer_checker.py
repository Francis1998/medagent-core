"""DOAC + strong inducer thrombosis-risk safety checker.

Strong CYP3A4/P-gp inducers can reduce DOAC exposure and increase
thrombotic risk. This DOAC-focused inducer control is distinct from
warfarin interaction checkers and from DOAC + NSAID / antiplatelet
bleeding controls.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DoacInducerRisk, Medication, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "apixaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "eliquis": "an apixaban brand direct oral anticoagulant",
    "rivaroxaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "xarelto": "a rivaroxaban brand direct oral anticoagulant",
    "edoxaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "savaysa": "an edoxaban brand direct oral anticoagulant",
    "dabigatran": "a direct oral anticoagulant (direct thrombin inhibitor)",
    "pradaxa": "a dabigatran brand direct oral anticoagulant",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "rifampin": (
        "a potent CYP3A4/P-gp inducer that can substantially reduce DOAC exposure",
        Severity.CRITICAL,
    ),
    "rifampicin": (
        "a rifampin spelling variant and potent CYP3A4/P-gp inducer",
        Severity.CRITICAL,
    ),
    "carbamazepine": (
        "a strong CYP3A4/P-gp-inducing antiepileptic",
        Severity.HIGH,
    ),
    "tegretol": (
        "a carbamazepine brand and strong CYP3A4/P-gp inducer",
        Severity.HIGH,
    ),
    "phenytoin": (
        "a strong CYP3A4/P-gp-inducing antiepileptic",
        Severity.HIGH,
    ),
    "dilantin": (
        "a phenytoin brand and strong CYP3A4/P-gp inducer",
        Severity.HIGH,
    ),
    "st johns wort": (
        "an herbal CYP3A4/P-gp inducer (Hypericum perforatum)",
        Severity.HIGH,
    ),
    "st john's wort": (
        "an herbal CYP3A4/P-gp inducer (Hypericum perforatum)",
        Severity.HIGH,
    ),
    "hypericum": (
        "St John's wort (Hypericum) herbal CYP3A4/P-gp inducer",
        Severity.HIGH,
    ),
}

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class DoacInducerChecker:
    """Flag DOAC therapy co-prescribed with strong CYP3A4/P-gp inducers."""

    def check(self, medications: list[Medication]) -> list[DoacInducerRisk]:
        """Return one finding per unique DOAC × inducer pair."""
        primary_matches: list[tuple[int, Medication, str]] = []
        partner_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            primary_agent = self._match_agent(medication.name, _PRIMARY_AGENTS)
            if primary_agent is not None:
                primary_matches.append((index, medication, primary_agent))

            partner_agent = self._match_agent(medication.name, _PARTNER_AGENTS)
            if partner_agent is not None:
                partner_matches.append((index, medication, partner_agent))

        if not primary_matches or not partner_matches:
            logger.info("doac_inducer_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[DoacInducerRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    DoacInducerRisk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=severity,
                        rationale=self._build_rationale(
                            primary_medication=primary_med.name,
                            primary_agent=primary_agent,
                            partner_medication=partner_med.name,
                            partner_agent=partner_agent,
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
        logger.info("doac_inducer_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        primary_medication: str,
        primary_agent: str,
        partner_medication: str,
        partner_agent: str,
    ) -> str:
        partner_descriptor, _severity = _PARTNER_AGENTS[partner_agent]
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{primary_medication}' contains {primary_agent}, "
            f"{_PRIMARY_AGENTS[primary_agent]}, and is co-prescribed with "
            f"'{partner_medication}' ({partner_agent}, {partner_descriptor}). "
            "Strong CYP3A4/P-gp induction can reduce DOAC anticoagulant "
            "exposure and increase thrombosis risk. Promptly review therapy "
            "with a qualified clinician; do not change therapy from this "
            "research output."
        )

    @staticmethod
    def _match_agent(
        name: str, agents: dict[str, str] | dict[str, tuple[str, Severity]]
    ) -> str | None:
        """Return the most specific whole-token/whole-alias match in ``name``."""
        lowered = name.lower()
        aliases = sorted(agents, key=lambda alias: (-len(alias.split()), -len(alias), alias))
        for alias in aliases:
            components = [re.escape(component) for component in alias.replace("-", " ").split()]
            pattern = r"(?<![a-z0-9])" + r"[\s_-]+".join(components) + r"(?![a-z0-9])"
            if re.search(pattern, lowered):
                return alias
        return None
