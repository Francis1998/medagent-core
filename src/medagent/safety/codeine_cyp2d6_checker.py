"""codeine + CYP2D6 inhibitor analgesia/exposure checker.

Codeine requires CYP2D6 bioactivation to morphine for analgesia. Strong
CYP2D6 inhibitors can reduce morphine formation, blunt analgesic effect,
and alter exposure. This focused control is distinct from opioid +
benzodiazepine, opioid MED, and tramadol interaction checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import CodeineCyp2d6Risk, Medication, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "codeine": "an opioid prodrug that requires CYP2D6 conversion to morphine",
    "tylenol-with-codeine": "a codeine-containing analgesic combination",
}

_PARTNER_AGENTS: Final[dict[str, str]] = {
    "fluoxetine": "a strong CYP2D6 inhibitor",
    "paroxetine": "a strong CYP2D6 inhibitor",
    "bupropion": "a strong CYP2D6 inhibitor",
    "quinidine": "a strong CYP2D6 inhibitor",
    "terbinafine": "a strong CYP2D6 inhibitor",
}


class CodeineCyp2d6Checker:
    """Flag codeine co-prescribed with a strong CYP2D6 inhibitor."""

    def check(self, medications: list[Medication]) -> list[CodeineCyp2d6Risk]:
        """Return one finding per unique codeine × CYP2D6-inhibitor pair."""
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
            logger.info("codeine_cyp2d6_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[CodeineCyp2d6Risk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    CodeineCyp2d6Risk(
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
        logger.info("codeine_cyp2d6_checked", findings=len(findings))
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
            f"{_PARTNER_AGENTS[partner_agent]}). Strong CYP2D6 inhibition can "
            "reduce codeine bioactivation to morphine, blunt analgesia, and "
            "alter exposure. Promptly review analgesic adequacy, alternatives, "
            "and patient-specific CYP2D6 considerations with a qualified "
            "clinician; do not change therapy from this research output."
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
