"""Methotrexate without folate co-therapy safety checker.

Long-term methotrexate therapy (especially in rheumatology and dermatology)
requires folic acid / folate / leucovorin co-therapy to reduce mucositis,
hematologic toxicity, and other antifolate adverse effects. Missing folate
rescue or supplementation is a preventable supportive-care gap distinct from
generic drug-drug interaction screening.

This checker flags methotrexate when no folic acid, folate, or leucovorin
co-therapy cue is present on the medication list. Whole-token matching is used
throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, MtxFolateRisk, Severity

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

# Canonical folate co-therapy token -> short descriptor.
_FOLATE_COTHERAPY_AGENTS: Final[dict[str, str]] = {
    "folic": "folic acid co-therapy",
    "folate": "folate co-therapy",
    "leucovorin": "leucovorin (folinic acid) rescue / co-therapy",
}


class MtxFolateChecker:
    """Flag methotrexate prescribed without folate co-therapy."""

    def check(self, medications: list[Medication]) -> list[MtxFolateRisk]:
        """Return findings for methotrexate without folate co-therapy.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`MtxFolateRisk` per unique methotrexate agent across
            distinct medication entries when no folate co-therapy cue is
            present, ordered by descending severity then medication name and
            agent. An empty list is returned when methotrexate is absent or
            folate co-therapy is present.
        """
        mtx_matches: list[tuple[Medication, str]] = []
        folate_agents_found: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            mtx_candidates = sorted(tokens & set(_METHOTREXATE_AGENTS))
            if mtx_candidates:
                mtx_matches.append((medication, mtx_candidates[0]))

            folate_hits = tokens & set(_FOLATE_COTHERAPY_AGENTS)
            if folate_hits:
                folate_agents_found.update(folate_hits)

        if not mtx_matches or folate_agents_found:
            logger.info(
                "mtx_folate_checked",
                findings=0,
                mtx_agents=len({agent for _med, agent in mtx_matches}),
                folate_agents=len(folate_agents_found),
            )
            return []

        findings: list[MtxFolateRisk] = []
        agents_seen: set[str] = set()

        for medication, agent in mtx_matches:
            if agent in agents_seen:
                continue
            agents_seen.add(agent)
            findings.append(
                MtxFolateRisk(
                    medication=medication.name,
                    agent=agent,
                    severity=Severity.HIGH,
                    rationale=self._build_rationale(
                        medication_name=medication.name,
                        agent=agent,
                        descriptor=_METHOTREXATE_AGENTS[agent],
                    ),
                )
            )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                finding.agent,
            )
        )
        logger.info(
            "mtx_folate_checked",
            findings=len(findings),
            mtx_agents=len(agents_seen),
            folate_agents=0,
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        medication_name: str,
        agent: str,
        descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY methotrexate-without-folate rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, {descriptor}, "
            "without documented folic acid, folate, or leucovorin co-therapy. "
            "Missing folate supplementation increases the risk of mucositis, "
            "hematologic toxicity, and other antifolate adverse effects. "
            "Review urgently and consider adding folic acid / folate / leucovorin "
            "per indication-specific guidance."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
