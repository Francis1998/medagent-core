"""Methotrexate + TMP-SMX toxicity interaction safety checker.

Trimethoprim–sulfamethoxazole (TMP-SMX / co-trimoxazole) can potentiate
methotrexate antifolate toxicity and increase myelosuppression risk. This
hazard is distinct from methotrexate-without-folate co-therapy screening and
generic drug-drug interaction flagging.

This checker flags methotrexate co-prescribed with TMP-SMX panel agents
(trimethoprim, sulfamethoxazole, bactrim, septra, cotrimoxazole). Whole-token
matching is used throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, MtxTmpsmxRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical methotrexate token -> short descriptor.
_METHOTREXATE_AGENTS: Final[dict[str, str]] = {
    "methotrexate": "an antifolate immunosuppressant / antineoplastic agent",
}

# Canonical TMP-SMX / co-trimoxazole panel token -> short descriptor.
_TMPSMX_AGENTS: Final[dict[str, str]] = {
    "trimethoprim": "a dihydrofolate-reductase inhibitor often combined as TMP-SMX",
    "sulfamethoxazole": "a sulfonamide antibiotic often combined as TMP-SMX",
    "bactrim": "a trimethoprim–sulfamethoxazole (TMP-SMX) brand formulation",
    "septra": "a trimethoprim–sulfamethoxazole (TMP-SMX) brand formulation",
    "cotrimoxazole": "trimethoprim–sulfamethoxazole (TMP-SMX / co-trimoxazole)",
}


class MtxTmpsmxChecker:
    """Flag methotrexate co-prescribed with TMP-SMX toxicity partners."""

    def check(self, medications: list[Medication]) -> list[MtxTmpsmxRisk]:
        """Return findings for each methotrexate × TMP-SMX pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`MtxTmpsmxRisk` per unique methotrexate × TMP-SMX agent
            pair across distinct medication entries, ordered by descending
            severity then methotrexate medication, partner medication, and
            agents. An empty list is returned when methotrexate or TMP-SMX
            panel agents are absent.
        """
        mtx_matches: list[tuple[Medication, str]] = []
        tmpsmx_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            mtx_candidates = sorted(tokens & set(_METHOTREXATE_AGENTS))
            if mtx_candidates:
                mtx_matches.append((medication, mtx_candidates[0]))

            tmpsmx_candidates = sorted(tokens & set(_TMPSMX_AGENTS))
            if tmpsmx_candidates:
                tmpsmx_matches.append((medication, tmpsmx_candidates[0]))

        if not mtx_matches or not tmpsmx_matches:
            logger.info("mtx_tmpsmx_checked", findings=0)
            return []

        findings: list[MtxTmpsmxRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for mtx_med, mtx_agent in mtx_matches:
            mtx_desc = _METHOTREXATE_AGENTS[mtx_agent]
            for tmpsmx_med, tmpsmx_agent in tmpsmx_matches:
                pair_key = (mtx_agent, tmpsmx_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                tmpsmx_desc = _TMPSMX_AGENTS[tmpsmx_agent]
                findings.append(
                    MtxTmpsmxRisk(
                        medication=mtx_med.name,
                        agent=mtx_agent,
                        partner_medication=tmpsmx_med.name,
                        partner_agent=tmpsmx_agent,
                        severity=Severity.CRITICAL,
                        rationale=self._build_rationale(
                            mtx_medication=mtx_med.name,
                            mtx_agent=mtx_agent,
                            mtx_descriptor=mtx_desc,
                            tmpsmx_medication=tmpsmx_med.name,
                            tmpsmx_agent=tmpsmx_agent,
                            tmpsmx_descriptor=tmpsmx_desc,
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
            "mtx_tmpsmx_checked",
            findings=len(findings),
            mtx_agents=len({agent for _med, agent in mtx_matches}),
            tmpsmx_agents=len({agent for _med, agent in tmpsmx_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        mtx_medication: str,
        mtx_agent: str,
        mtx_descriptor: str,
        tmpsmx_medication: str,
        tmpsmx_agent: str,
        tmpsmx_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY methotrexate × TMP-SMX rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{mtx_medication}' contains {mtx_agent}, "
            f"{mtx_descriptor}, and is co-prescribed with '{tmpsmx_medication}' "
            f"({tmpsmx_agent}, {tmpsmx_descriptor}). Trimethoprim–sulfamethoxazole "
            "can potentiate methotrexate antifolate toxicity and increase "
            "myelosuppression risk. Review urgently; consider avoiding the "
            "combination, closer CBC / methotrexate-toxicity monitoring, or an "
            "alternative antibiotic when clinically appropriate."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
