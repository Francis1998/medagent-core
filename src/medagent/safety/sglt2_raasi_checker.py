"""SGLT2 inhibitor + ACEI/ARB/ARNI hyperkalemia / volume-depletion safety checker.

SGLT2 inhibitors promote osmotic diuresis and can raise the risk of volume
depletion and acute kidney injury when combined with renin–angiotensin system
agents. Concurrent RAAS blockade also increases hyperkalemia risk. This hazard
is distinct from SGLT2 + loop diuretic screening and focused ACEI/ARB
duplication or potassium-sparing hyperkalemia controls.

This checker flags SGLT2 inhibitors (empagliflozin, dapagliflozin, canagliflozin,
ertugliflozin) co-prescribed with ACE inhibitors, ARBs, or ARNIs. Whole-token
matching is used throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, Sglt2RaasiRisk

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_SGLT2_AGENTS: Final[dict[str, str]] = {
    "empagliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
    "dapagliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
    "canagliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
    "ertugliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
}

_RAASI_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "lisinopril": ("an ACE inhibitor", Severity.HIGH),
    "enalapril": ("an ACE inhibitor", Severity.HIGH),
    "ramipril": ("an ACE inhibitor", Severity.HIGH),
    "benazepril": ("an ACE inhibitor", Severity.HIGH),
    "quinapril": ("an ACE inhibitor", Severity.HIGH),
    "captopril": ("an ACE inhibitor", Severity.HIGH),
    "fosinopril": ("an ACE inhibitor", Severity.HIGH),
    "perindopril": ("an ACE inhibitor", Severity.HIGH),
    "trandolapril": ("an ACE inhibitor", Severity.HIGH),
    "moexipril": ("an ACE inhibitor", Severity.HIGH),
    "losartan": ("an angiotensin receptor blocker", Severity.HIGH),
    "valsartan": ("an angiotensin receptor blocker", Severity.HIGH),
    "olmesartan": ("an angiotensin receptor blocker", Severity.HIGH),
    "candesartan": ("an angiotensin receptor blocker", Severity.HIGH),
    "irbesartan": ("an angiotensin receptor blocker", Severity.HIGH),
    "telmisartan": ("an angiotensin receptor blocker", Severity.HIGH),
    "sacubitril": ("an ARNI component (neprilysin inhibitor)", Severity.HIGH),
    "entresto": ("a sacubitril/valsartan (ARNI) brand formulation", Severity.HIGH),
}


class Sglt2RaasiChecker:
    """Flag SGLT2 inhibitors co-prescribed with ACEI/ARB/ARNI RAAS agents."""

    def check(self, medications: list[Medication]) -> list[Sglt2RaasiRisk]:
        """Return one finding per unique SGLT2 × RAASI pair."""
        sglt2_matches: list[tuple[int, Medication, str]] = []
        raasi_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            sglt2_candidates = sorted(tokens & set(_SGLT2_AGENTS))
            if sglt2_candidates:
                sglt2_matches.append((index, medication, sglt2_candidates[0]))

            raasi_candidates = sorted(tokens & set(_RAASI_AGENTS))
            if raasi_candidates:
                raasi_matches.append((index, medication, raasi_candidates[0]))

        if not sglt2_matches or not raasi_matches:
            logger.info("sglt2_raasi_checked", findings=0)
            return []

        sglt2_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        raasi_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))

        findings: list[Sglt2RaasiRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for sglt2_index, sglt2_med, sglt2_agent in sglt2_matches:
            for raasi_index, raasi_med, raasi_agent in raasi_matches:
                if sglt2_index == raasi_index:
                    continue
                pair_key = (sglt2_agent, raasi_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                raasi_desc, severity = _RAASI_AGENTS[raasi_agent]
                findings.append(
                    Sglt2RaasiRisk(
                        medication=sglt2_med.name,
                        agent=sglt2_agent,
                        partner_medication=raasi_med.name,
                        partner_agent=raasi_agent,
                        severity=severity,
                        rationale=self._build_rationale(
                            sglt2_medication=sglt2_med.name,
                            sglt2_agent=sglt2_agent,
                            sglt2_descriptor=_SGLT2_AGENTS[sglt2_agent],
                            raasi_medication=raasi_med.name,
                            raasi_agent=raasi_agent,
                            raasi_descriptor=raasi_desc,
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
        logger.info(
            "sglt2_raasi_checked",
            findings=len(findings),
            sglt2_agents=len({agent for _index, _medication, agent in sglt2_matches}),
            raasi_agents=len({agent for _index, _medication, agent in raasi_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        sglt2_medication: str,
        sglt2_agent: str,
        sglt2_descriptor: str,
        raasi_medication: str,
        raasi_agent: str,
        raasi_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY SGLT2 × RAASI rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{sglt2_medication}' contains {sglt2_agent}, "
            f"{sglt2_descriptor}, and is co-prescribed with '{raasi_medication}' "
            f"({raasi_agent}, {raasi_descriptor}). Concurrent SGLT2 inhibitor and "
            "ACEI/ARB/ARNI therapy increases volume depletion, hypotension, acute "
            "kidney injury, and hyperkalemia risk. Review urgently; assess volume "
            "status, renal function, and serum potassium with a qualified clinician; "
            "do not change therapy from this research output."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
