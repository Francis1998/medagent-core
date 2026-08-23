"""Metformin + iodinated contrast media lactic acidosis checker.

Iodinated contrast media used in imaging studies can transiently impair renal
function; when renal clearance of metformin is reduced, the biguanide can
accumulate and precipitate life-threatening lactic acidosis. This focused
peri-contrast control is distinct from general metformin renal-dose checking.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, MetforminContrastRisk, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "metformin": "a biguanide antihyperglycemic",
    "glucophage": "a metformin brand formulation",
    "fortamet": "a metformin brand formulation",
    "glumetza": "a metformin brand formulation",
    "riomet": "a metformin brand formulation",
}

_PARTNER_AGENTS: Final[dict[str, str]] = {
    "contrast": "an iodinated contrast medium",
    "contrast-media": "an iodinated contrast medium",
    "iohexol": "an iodinated contrast medium",
    "iodixanol": "an iodinated contrast medium",
    "iopamidol": "an iodinated contrast medium",
}


class MetforminContrastChecker:
    """Flag metformin therapy co-prescribed with iodinated contrast media."""

    def check(self, medications: list[Medication]) -> list[MetforminContrastRisk]:
        """Return one finding per unique metformin × contrast-media pair."""
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
            logger.info("metformin_contrast_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[MetforminContrastRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    MetforminContrastRisk(
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
        logger.info("metformin_contrast_checked", findings=len(findings))
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
            f"{_PARTNER_AGENTS[partner_agent]}). Iodinated contrast can transiently "
            "impair renal clearance of metformin, and accumulation can precipitate "
            "life-threatening lactic acidosis. Promptly review renal function, "
            "peri-procedure metformin hold/resume timing, and hydration status with "
            "a qualified clinician; do not change therapy from this research output."
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
