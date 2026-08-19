"""Amiodarone + digoxin P-glycoprotein interaction safety checker.

Amiodarone inhibits P-glycoprotein and reduces digoxin clearance, which can
substantially raise serum digoxin concentrations and toxicity risk. This
amiodarone-first control is distinct from digoxin + verapamil screening.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AmiodaroneDigoxinRisk, Medication, Severity

logger = get_logger(__name__)

_AMIODARONE_AGENTS: Final[dict[str, str]] = {
    "amiodarone": "a class III antiarrhythmic and P-glycoprotein inhibitor",
    "cordarone": "an amiodarone brand formulation and P-glycoprotein inhibitor",
    "pacerone": "an amiodarone brand formulation and P-glycoprotein inhibitor",
}

_DIGOXIN_AGENTS: Final[dict[str, str]] = {
    "digoxin": "a cardiac glycoside with a narrow therapeutic index",
    "lanoxin": "a digoxin brand formulation with a narrow therapeutic index",
}


class AmiodaroneDigoxinChecker:
    """Flag amiodarone co-prescribed with digoxin."""

    def check(self, medications: list[Medication]) -> list[AmiodaroneDigoxinRisk]:
        """Return one finding per unique amiodarone × digoxin pair."""
        amiodarone_matches: list[tuple[int, Medication, str]] = []
        digoxin_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            amiodarone_candidates = sorted(tokens & set(_AMIODARONE_AGENTS))
            if amiodarone_candidates:
                amiodarone_matches.append((index, medication, amiodarone_candidates[0]))

            digoxin_candidates = sorted(tokens & set(_DIGOXIN_AGENTS))
            if digoxin_candidates:
                digoxin_matches.append((index, medication, digoxin_candidates[0]))

        if not amiodarone_matches or not digoxin_matches:
            logger.info("amiodarone_digoxin_checked", findings=0)
            return []

        amiodarone_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        digoxin_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[AmiodaroneDigoxinRisk] = []
        seen: set[tuple[str, str]] = set()

        for amiodarone_index, amiodarone_med, amiodarone_agent in amiodarone_matches:
            for digoxin_index, digoxin_med, digoxin_agent in digoxin_matches:
                pair_key = (amiodarone_agent, digoxin_agent)
                if amiodarone_index == digoxin_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                findings.append(
                    AmiodaroneDigoxinRisk(
                        medication=amiodarone_med.name,
                        agent=amiodarone_agent,
                        partner_medication=digoxin_med.name,
                        partner_agent=digoxin_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            amiodarone_medication=amiodarone_med.name,
                            amiodarone_agent=amiodarone_agent,
                            digoxin_medication=digoxin_med.name,
                            digoxin_agent=digoxin_agent,
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
        logger.info("amiodarone_digoxin_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        amiodarone_medication: str,
        amiodarone_agent: str,
        digoxin_medication: str,
        digoxin_agent: str,
    ) -> str:
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{amiodarone_medication}' contains {amiodarone_agent}, "
            f"{_AMIODARONE_AGENTS[amiodarone_agent]}, and is co-prescribed with "
            f"'{digoxin_medication}' ({digoxin_agent}, {_DIGOXIN_AGENTS[digoxin_agent]}). "
            "Amiodarone inhibits P-glycoprotein and reduces digoxin clearance, which "
            "can substantially increase serum digoxin concentrations and toxicity risk. "
            "Promptly review digoxin dose, renal function, and serum-level monitoring "
            "with a qualified clinician; do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", name.lower()))
