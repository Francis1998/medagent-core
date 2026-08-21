"""tramadol + bupropion seizure-risk checker.

Both agents lower the seizure threshold, so concurrent use can compound
seizure risk. This focused control is distinct from tramadol + SSRI/SNRI
screening.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, TramadolBupropionRisk

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "tramadol": "an opioid analgesic that lowers the seizure threshold",
    "ultram": "a tramadol brand formulation that lowers the seizure threshold",
}

_PARTNER_AGENTS: Final[dict[str, str]] = {
    "bupropion": "an antidepressant that lowers the seizure threshold",
    "wellbutrin": "a bupropion brand formulation that lowers the seizure threshold",
    "zyban": "a bupropion brand formulation that lowers the seizure threshold",
}


class TramadolBupropionChecker:
    """Flag tramadol-class therapy co-prescribed with bupropion-class therapy."""

    def check(self, medications: list[Medication]) -> list[TramadolBupropionRisk]:
        """Return one finding per unique tramadol × bupropion pair."""
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
            logger.info("tramadol_bupropion_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[TramadolBupropionRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    TramadolBupropionRisk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=Severity.HIGH,
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
                finding.medication.lower(),
                finding.partner_medication.lower(),
                finding.agent,
                finding.partner_agent,
            )
        )
        logger.info("tramadol_bupropion_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        primary_medication: str,
        primary_agent: str,
        partner_medication: str,
        partner_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{primary_medication}' contains {primary_agent}, "
            f"{_PRIMARY_AGENTS[primary_agent]}, and is co-prescribed with "
            f"'{partner_medication}' ({partner_agent}, "
            f"{_PARTNER_AGENTS[partner_agent]}). Both tramadol and bupropion "
            "lower the seizure threshold, so concurrent use can compound seizure "
            "risk. Promptly review patient-specific seizure risk, doses, and "
            "alternatives with a qualified clinician; do not change therapy from "
            "this research output."
        )

    @staticmethod
    def _match_agent(name: str, agents: dict[str, str]) -> str | None:
        """Return the most specific whole-token/whole-alias match in ``name``."""
        lowered = name.lower()
        aliases = sorted(agents, key=lambda alias: (-len(alias.split("-")), alias))
        for alias in aliases:
            components = [re.escape(component) for component in alias.split("-")]
            pattern = r"(?<![a-z0-9])" + r"[\s_-]+".join(components) + r"(?![a-z0-9])"
            if re.search(pattern, lowered):
                return alias
        return None
