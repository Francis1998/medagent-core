"""Linezolid + SSRI/SNRI serotonin-syndrome safety checker.

Linezolid has reversible MAOI-like activity. Co-prescription with supported
SSRIs or SNRIs can precipitate serotonin syndrome. This focused hazard is
distinct from tramadol + SSRI/SNRI and SSRI/SNRI + triptan controls.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import LinezolidSsriRisk, Medication, Severity

logger = get_logger(__name__)

_LINEZOLID_AGENTS: Final[dict[str, str]] = {
    "linezolid": "an oxazolidinone antibiotic with reversible MAOI-like activity",
}

_SSRI_SNRI_AGENTS: Final[dict[str, str]] = {
    "sertraline": "an SSRI",
    "fluoxetine": "an SSRI",
    "paroxetine": "an SSRI",
    "citalopram": "an SSRI",
    "escitalopram": "an SSRI",
    "venlafaxine": "an SNRI",
    "duloxetine": "an SNRI",
}


class LinezolidSsriChecker:
    """Flag linezolid co-prescribed with a supported SSRI or SNRI."""

    def check(self, medications: list[Medication]) -> list[LinezolidSsriRisk]:
        """Return one finding per unique linezolid × SSRI/SNRI pair."""
        linezolid_matches: list[tuple[int, Medication, str]] = []
        serotonergic_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            linezolid_candidates = sorted(tokens & set(_LINEZOLID_AGENTS))
            if linezolid_candidates:
                linezolid_matches.append((index, medication, linezolid_candidates[0]))
            serotonergic_candidates = sorted(tokens & set(_SSRI_SNRI_AGENTS))
            if serotonergic_candidates:
                serotonergic_matches.append((index, medication, serotonergic_candidates[0]))

        if not linezolid_matches or not serotonergic_matches:
            logger.info("linezolid_ssri_checked", findings=0)
            return []

        linezolid_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        serotonergic_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[LinezolidSsriRisk] = []
        seen: set[tuple[str, str]] = set()

        for linezolid_index, linezolid_med, linezolid_agent in linezolid_matches:
            for partner_index, partner_med, partner_agent in serotonergic_matches:
                if linezolid_index == partner_index or (linezolid_agent, partner_agent) in seen:
                    continue
                seen.add((linezolid_agent, partner_agent))
                findings.append(
                    LinezolidSsriRisk(
                        medication=linezolid_med.name,
                        agent=linezolid_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=Severity.CRITICAL,
                        rationale=self._build_rationale(
                            linezolid_med.name,
                            linezolid_agent,
                            partner_med.name,
                            partner_agent,
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
        logger.info("linezolid_ssri_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        linezolid_medication: str,
        linezolid_agent: str,
        partner_medication: str,
        partner_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{linezolid_medication}' contains {linezolid_agent}, "
            f"{_LINEZOLID_AGENTS[linezolid_agent]}, and is co-prescribed with "
            f"'{partner_medication}' ({partner_agent}, "
            f"{_SSRI_SNRI_AGENTS[partner_agent]}). This combination can precipitate "
            "potentially life-threatening serotonin syndrome. Obtain urgent qualified "
            "clinical review and monitor for compatible symptoms; do not change therapy "
            "from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
