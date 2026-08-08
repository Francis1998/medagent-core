"""Clozapine ANC (absolute neutrophil count) monitoring safety checker.

Clozapine carries a boxed warning for severe neutropenia / agranulocytosis and
requires scheduled absolute neutrophil count (ANC) monitoring under REMS-style
programs. Missing or unprompted ANC surveillance is a preventable hematologic
safety gap distinct from generic boxed-warning panels and drug-drug interaction
screening.

This checker emits a monitoring finding whenever a clozapine-class agent
(clozapine, Clozaril, or FazaClo) is present on the medication list. Whole-token
matching is used throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import ClozapineAncRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical clozapine-class token -> short descriptor.
_CLOZAPINE_AGENTS: Final[dict[str, str]] = {
    "clozapine": "an atypical antipsychotic with agranulocytosis risk",
    "clozaril": "a clozapine brand formulation with agranulocytosis risk",
    "fazaclo": "an orally disintegrating clozapine brand with agranulocytosis risk",
}


class ClozapineAncChecker:
    """Flag clozapine-class therapy and emit an ANC monitoring reminder."""

    def check(self, medications: list[Medication]) -> list[ClozapineAncRisk]:
        """Return ANC monitoring findings for each unique clozapine-class agent.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`ClozapineAncRisk` per unique clozapine-class agent across
            distinct medication entries, ordered by descending severity then
            medication name and agent. An empty list is returned when no
            clozapine-class agent is present.
        """
        clozapine_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            candidates = sorted(tokens & set(_CLOZAPINE_AGENTS))
            if candidates:
                clozapine_matches.append((medication, candidates[0]))

        if not clozapine_matches:
            logger.info("clozapine_anc_checked", findings=0)
            return []

        findings: list[ClozapineAncRisk] = []
        agents_seen: set[str] = set()

        for medication, agent in clozapine_matches:
            if agent in agents_seen:
                continue
            agents_seen.add(agent)
            findings.append(
                ClozapineAncRisk(
                    medication=medication.name,
                    agent=agent,
                    severity=Severity.CRITICAL,
                    rationale=self._build_rationale(
                        medication_name=medication.name,
                        agent=agent,
                        descriptor=_CLOZAPINE_AGENTS[agent],
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
            "clozapine_anc_checked",
            findings=len(findings),
            clozapine_agents=len(agents_seen),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        medication_name: str,
        agent: str,
        descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY clozapine ANC monitoring rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, {descriptor}. "
            "Clozapine can cause severe neutropenia and agranulocytosis; confirm "
            "absolute neutrophil count (ANC) / neutrophil monitoring is current "
            "per REMS-style guidance before continuing therapy, and review urgently "
            "if monitoring cues are absent."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
