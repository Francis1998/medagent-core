"""SGLT2 inhibitor + loop diuretic volume-depletion safety checker.

Sodium-glucose cotransporter-2 (SGLT2) inhibitors promote osmotic diuresis, and
loop diuretics further increase urinary losses. Co-prescription elevates volume
depletion, hypotension, and acute kidney injury risk — a hazard distinct from
the triple-whammy (NSAID + ACEI/ARB + diuretic) check and generic drug-drug
interaction screening.

This checker flags SGLT2 inhibitors (empagliflozin, dapagliflozin, canagliflozin,
ertugliflozin) co-prescribed with loop diuretics (furosemide, bumetanide,
torsemide, ethacrynic). Whole-token matching is used throughout. Findings are
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, Sglt2LoopRisk

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical SGLT2 inhibitor token -> short descriptor.
_SGLT2_AGENTS: Final[dict[str, str]] = {
    "empagliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
    "dapagliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
    "canagliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
    "ertugliflozin": "an SGLT2 inhibitor that promotes osmotic diuresis",
}

# Canonical loop diuretic token -> short descriptor.
_LOOP_DIURETICS: Final[dict[str, str]] = {
    "furosemide": "a loop diuretic that increases urinary volume loss",
    "bumetanide": "a loop diuretic that increases urinary volume loss",
    "torsemide": "a loop diuretic that increases urinary volume loss",
    "ethacrynic": "a loop diuretic (ethacrynic acid) that increases urinary volume loss",
}


class Sglt2LoopChecker:
    """Flag SGLT2 inhibitors co-prescribed with loop diuretics."""

    def check(self, medications: list[Medication]) -> list[Sglt2LoopRisk]:
        """Return findings for each SGLT2 × loop diuretic pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`Sglt2LoopRisk` per unique SGLT2 × loop agent pair across
            distinct medication entries, ordered by descending severity then
            SGLT2 medication, partner medication, and agents. An empty list is
            returned when SGLT2 inhibitors or loop diuretics are absent.
        """
        sglt2_matches: list[tuple[Medication, str]] = []
        loop_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            sglt2_candidates = sorted(tokens & set(_SGLT2_AGENTS))
            if sglt2_candidates:
                sglt2_matches.append((medication, sglt2_candidates[0]))

            loop_candidates = sorted(tokens & set(_LOOP_DIURETICS))
            if loop_candidates:
                loop_matches.append((medication, loop_candidates[0]))

        if not sglt2_matches or not loop_matches:
            logger.info("sglt2_loop_checked", findings=0)
            return []

        findings: list[Sglt2LoopRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for sglt2_med, sglt2_agent in sglt2_matches:
            sglt2_desc = _SGLT2_AGENTS[sglt2_agent]
            for loop_med, loop_agent in loop_matches:
                pair_key = (sglt2_agent, loop_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                loop_desc = _LOOP_DIURETICS[loop_agent]
                findings.append(
                    Sglt2LoopRisk(
                        medication=sglt2_med.name,
                        agent=sglt2_agent,
                        partner_medication=loop_med.name,
                        partner_agent=loop_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            sglt2_medication=sglt2_med.name,
                            sglt2_agent=sglt2_agent,
                            sglt2_descriptor=sglt2_desc,
                            loop_medication=loop_med.name,
                            loop_agent=loop_agent,
                            loop_descriptor=loop_desc,
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
            "sglt2_loop_checked",
            findings=len(findings),
            sglt2_agents=len({agent for _med, agent in sglt2_matches}),
            loop_agents=len({agent for _med, agent in loop_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        sglt2_medication: str,
        sglt2_agent: str,
        sglt2_descriptor: str,
        loop_medication: str,
        loop_agent: str,
        loop_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY SGLT2 × loop diuretic rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{sglt2_medication}' contains {sglt2_agent}, "
            f"{sglt2_descriptor}, and is co-prescribed with '{loop_medication}' "
            f"({loop_agent}, {loop_descriptor}). Concurrent SGLT2 inhibitor and "
            "loop diuretic therapy increases volume depletion, hypotension, and "
            "acute kidney injury risk. Review urgently; consider dose adjustment, "
            "volume status assessment, and closer renal monitoring."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
