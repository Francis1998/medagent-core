"""sildenafil + nitrate critical hypotension checker.

PDE-5 inhibition amplifies nitrate-mediated cyclic-GMP vasodilation and
can cause profound, life-threatening hypotension. This focused control is
distinct from non-nitrate antianginal and antihypertensive screening.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, SildenafilNitrateRisk

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "sildenafil": "a phosphodiesterase-5 inhibitor",
    "viagra": "a sildenafil brand formulation",
    "revatio": "a sildenafil brand formulation",
}

_PARTNER_AGENTS: Final[dict[str, str]] = {
    "nitroglycerin": "an organic nitrate vasodilator",
    "isosorbide": "an organic nitrate vasodilator",
    "imdur": "an isosorbide mononitrate brand formulation",
    "monoket": "an isosorbide mononitrate brand formulation",
}


class SildenafilNitrateChecker:
    """Flag sildenafil-class therapy co-prescribed with nitrate therapy."""

    def check(self, medications: list[Medication]) -> list[SildenafilNitrateRisk]:
        """Return one finding per unique sildenafil × nitrate pair."""
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
            logger.info("sildenafil_nitrate_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[SildenafilNitrateRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    SildenafilNitrateRisk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=Severity.CRITICAL,
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
        logger.info("sildenafil_nitrate_checked", findings=len(findings))
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
            f"{_PARTNER_AGENTS[partner_agent]}). PDE-5 inhibition amplifies "
            "nitrate-mediated cyclic-GMP vasodilation and can cause profound, "
            "life-threatening hypotension, syncope, ischemia, or shock. Treat "
            "this combination as requiring immediate qualified-clinician "
            "review; do not change therapy from this research output."
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
