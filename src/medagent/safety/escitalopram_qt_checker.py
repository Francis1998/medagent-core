"""Escitalopram / citalopram QT-prolongation safety checker.

Escitalopram (Lexapro) and citalopram (Celexa) carry dose-dependent QT
prolongation risk. Presence alone is a HIGH QT-risk finding; co-prescription
with other known QT-prolonging agents escalates severity to CRITICAL. This
SSRI-specific QT control is distinct from quetiapine CYP3A4 exposure checks
and from the general multi-drug QT-prolongation screen.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import EscitalopramQtRisk, Medication, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "escitalopram": "an SSRI with dose-dependent QT prolongation",
    "lexapro": "an escitalopram brand SSRI with QT-prolongation risk",
    "citalopram": "an SSRI with dose-dependent QT prolongation",
    "celexa": "a citalopram brand SSRI with QT-prolongation risk",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ondansetron": (
        "a 5-HT3 antagonist antiemetic and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "zofran": (
        "an ondansetron brand antiemetic and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "haloperidol": (
        "a butyrophenone antipsychotic and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "haldol": (
        "a haloperidol brand antipsychotic and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "amiodarone": (
        "a class III antiarrhythmic and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "cordarone": (
        "an amiodarone brand antiarrhythmic and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "levofloxacin": (
        "a fluoroquinolone antibiotic and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "levaquin": (
        "a levofloxacin brand fluoroquinolone and QT-prolonging agent",
        Severity.CRITICAL,
    ),
    "azithromycin": (
        "a macrolide antibiotic and QT-prolonging agent",
        Severity.HIGH,
    ),
    "zithromax": (
        "an azithromycin brand macrolide and QT-prolonging agent",
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

_ALONE_SEVERITY: Final[Severity] = Severity.HIGH


class EscitalopramQtChecker:
    """Flag escitalopram/citalopram QT risk alone and escalate with QT partners."""

    def check(self, medications: list[Medication]) -> list[EscitalopramQtRisk]:
        """Return solo HIGH findings and/or escalated pair findings."""
        primary_matches: list[tuple[int, Medication, str]] = []
        partner_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            primary_agent = self._match_agent(medication.name, _PRIMARY_AGENTS)
            if primary_agent is not None:
                primary_matches.append((index, medication, primary_agent))

            partner_agent = self._match_agent(medication.name, _PARTNER_AGENTS)
            if partner_agent is not None:
                partner_matches.append((index, medication, partner_agent))

        if not primary_matches:
            logger.info("escitalopram_qt_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[EscitalopramQtRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    EscitalopramQtRisk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=severity,
                        rationale=self._build_pair_rationale(
                            primary_medication=primary_med.name,
                            primary_agent=primary_agent,
                            partner_medication=partner_med.name,
                            partner_agent=partner_agent,
                        ),
                    )
                )

        if not findings:
            seen_solo: set[str] = set()
            for _primary_index, primary_med, primary_agent in primary_matches:
                if primary_agent in seen_solo:
                    continue
                seen_solo.add(primary_agent)
                findings.append(
                    EscitalopramQtRisk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication="",
                        partner_agent="",
                        severity=_ALONE_SEVERITY,
                        rationale=self._build_alone_rationale(
                            primary_medication=primary_med.name,
                            primary_agent=primary_agent,
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
        logger.info("escitalopram_qt_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_alone_rationale(*, primary_medication: str, primary_agent: str) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{primary_medication}' contains {primary_agent}, "
            f"{_PRIMARY_AGENTS[primary_agent]}. Escitalopram/citalopram carry "
            "dose-dependent QT-prolongation and torsades de pointes risk even "
            "as monotherapy at risk doses. Obtain ECG/QTc monitoring and "
            "qualified clinical review; do not change therapy from this "
            "research output."
        )

    @staticmethod
    def _build_pair_rationale(
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
            "Escitalopram/citalopram QT-prolonging effect is intensified by a "
            "second QT-prolonging agent, escalating torsades de pointes risk. "
            "Obtain urgent ECG/QTc monitoring and qualified clinical and "
            "pharmacist review; do not change therapy from this research output."
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
