"""Quetiapine + strong CYP3A4 inhibitor QT/sedation exposure safety checker.

Strong CYP3A4 inhibitors can markedly increase quetiapine exposure and
intensify QT-prolongation and sedation risk. This quetiapine-focused CYP3A4
control is distinct from the colchicine CYP3A4/P-gp and fentanyl CYP3A4
checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, QuetiapineCyp3a4Risk, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "quetiapine": "an atypical antipsychotic metabolized primarily by CYP3A4",
    "seroquel": "a quetiapine brand atypical antipsychotic",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ketoconazole": (
        "an azole antifungal and strong CYP3A4 inhibitor",
        Severity.CRITICAL,
    ),
    "itraconazole": (
        "an azole antifungal and strong CYP3A4 inhibitor",
        Severity.CRITICAL,
    ),
    "ritonavir": (
        "an HIV protease inhibitor and strong CYP3A4 inhibitor",
        Severity.CRITICAL,
    ),
    "cobicistat": (
        "a pharmacokinetic booster and strong CYP3A4 inhibitor",
        Severity.CRITICAL,
    ),
    "clarithromycin": (
        "a macrolide antibiotic and strong CYP3A4 inhibitor",
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


class QuetiapineCyp3a4Checker:
    """Flag quetiapine co-prescribed with strong CYP3A4 inhibitors."""

    def check(self, medications: list[Medication]) -> list[QuetiapineCyp3a4Risk]:
        """Return one finding per unique quetiapine × inhibitor pair."""
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
            logger.info("quetiapine_cyp3a4_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[QuetiapineCyp3a4Risk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    QuetiapineCyp3a4Risk(
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
        logger.info("quetiapine_cyp3a4_checked", findings=len(findings))
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
            "Strong CYP3A4 inhibition can markedly increase quetiapine "
            "exposure and intensify QT-prolongation and sedation risk. "
            "Obtain urgent qualified clinical and pharmacist review; do not "
            "change therapy from this research output."
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
