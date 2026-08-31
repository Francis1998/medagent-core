"""Spironolactone / eplerenone + potassium hyperkalemia safety checker.

Mineralocorticoid receptor antagonists (spironolactone/Aldactone,
eplerenone/Inspra) reduce renal potassium excretion; co-prescribed potassium
supplements or potassium-containing salt substitutes intensify hyperkalemia
risk. This MRA-focused control is distinct from ACEI/ARB + potassium
(`acei_potassium_checker.py`) and ACEI/ARB + potassium-sparing diuretic
(`acei_ksparing_checker.py`) screening.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, SpironolactonePotassiumRisk

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "spironolactone": "a mineralocorticoid receptor antagonist (potassium-sparing)",
    "aldactone": "a spironolactone brand mineralocorticoid receptor antagonist",
    "eplerenone": "a selective mineralocorticoid receptor antagonist",
    "inspra": "an eplerenone brand mineralocorticoid receptor antagonist",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "potassium-chloride": (
        "a potassium chloride supplement",
        Severity.CRITICAL,
    ),
    "kcl": (
        "a potassium chloride supplement",
        Severity.CRITICAL,
    ),
    "klor-con": (
        "a potassium chloride brand formulation",
        Severity.CRITICAL,
    ),
    "potassium": (
        "a potassium supplement",
        Severity.CRITICAL,
    ),
    "salt-substitute": (
        "a potassium-containing salt substitute",
        Severity.HIGH,
    ),
    "no-salt": (
        "a potassium-based salt substitute",
        Severity.HIGH,
    ),
    "nosalt": (
        "a potassium-based salt substitute",
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


class SpironolactonePotassiumChecker:
    """Flag MRA therapy co-prescribed with potassium / salt substitutes."""

    def check(self, medications: list[Medication]) -> list[SpironolactonePotassiumRisk]:
        """Return one finding per unique MRA × potassium-source pair."""
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
            logger.info("spironolactone_potassium_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[SpironolactonePotassiumRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    SpironolactonePotassiumRisk(
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
        logger.info("spironolactone_potassium_checked", findings=len(findings))
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
            "Mineralocorticoid receptor antagonism plus exogenous potassium "
            "or potassium salt substitutes intensifies hyperkalemia risk. "
            "Promptly review serum potassium, renal function, and the need for "
            "supplementation with a qualified clinician; do not change therapy "
            "from this research output."
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
