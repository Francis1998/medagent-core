"""Lithium + NSAID toxicity interaction safety checker.

NSAIDs can reduce renal lithium clearance and raise lithium serum
concentrations, increasing toxicity risk. This hazard is distinct from
lactation, pregnancy, renal-dose, and generic drug-drug interaction screening.

This checker flags lithium-class agents (lithium, Lithobid, Eskalith)
co-prescribed with NSAIDs (ibuprofen, naproxen, diclofenac, indomethacin,
ketorolac, meloxicam, piroxicam, celecoxib). Acetaminophen/paracetamol are
intentionally excluded. Whole-token matching is used throughout. Findings are
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import LithiumNsaidRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical lithium-class token -> short descriptor.
_LITHIUM_AGENTS: Final[dict[str, str]] = {
    "lithium": "a mood stabilizer with a narrow therapeutic index",
    "lithobid": "a lithium brand formulation with a narrow therapeutic index",
    "eskalith": "a lithium brand formulation with a narrow therapeutic index",
}

# Canonical NSAID token -> short descriptor.
# Acetaminophen/paracetamol intentionally omitted (not NSAIDs).
_NSAID_AGENTS: Final[dict[str, str]] = {
    "ibuprofen": "an NSAID that can reduce renal lithium clearance",
    "naproxen": "an NSAID that can reduce renal lithium clearance",
    "diclofenac": "an NSAID that can reduce renal lithium clearance",
    "indomethacin": "an NSAID that can reduce renal lithium clearance",
    "ketorolac": "an NSAID that can reduce renal lithium clearance",
    "meloxicam": "an NSAID that can reduce renal lithium clearance",
    "piroxicam": "an NSAID that can reduce renal lithium clearance",
    "celecoxib": "a COX-2 selective NSAID that can reduce renal lithium clearance",
}


class LithiumNsaidChecker:
    """Flag lithium-class agents co-prescribed with NSAIDs."""

    def check(self, medications: list[Medication]) -> list[LithiumNsaidRisk]:
        """Return findings for each lithium × NSAID pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`LithiumNsaidRisk` per unique lithium × NSAID agent pair
            across distinct medication entries, ordered by descending severity
            then lithium medication, partner medication, and agents. An empty
            list is returned when lithium-class agents or NSAIDs are absent.
        """
        lithium_matches: list[tuple[Medication, str]] = []
        nsaid_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            lithium_candidates = sorted(tokens & set(_LITHIUM_AGENTS))
            if lithium_candidates:
                lithium_matches.append((medication, lithium_candidates[0]))

            nsaid_candidates = sorted(tokens & set(_NSAID_AGENTS))
            if nsaid_candidates:
                nsaid_matches.append((medication, nsaid_candidates[0]))

        if not lithium_matches or not nsaid_matches:
            logger.info("lithium_nsaid_checked", findings=0)
            return []

        findings: list[LithiumNsaidRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for lithium_med, lithium_agent in lithium_matches:
            lithium_desc = _LITHIUM_AGENTS[lithium_agent]
            for nsaid_med, nsaid_agent in nsaid_matches:
                pair_key = (lithium_agent, nsaid_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                nsaid_desc = _NSAID_AGENTS[nsaid_agent]
                findings.append(
                    LithiumNsaidRisk(
                        medication=lithium_med.name,
                        agent=lithium_agent,
                        partner_medication=nsaid_med.name,
                        partner_agent=nsaid_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            lithium_medication=lithium_med.name,
                            lithium_agent=lithium_agent,
                            lithium_descriptor=lithium_desc,
                            nsaid_medication=nsaid_med.name,
                            nsaid_agent=nsaid_agent,
                            nsaid_descriptor=nsaid_desc,
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
            "lithium_nsaid_checked",
            findings=len(findings),
            lithium_agents=len({agent for _med, agent in lithium_matches}),
            nsaid_agents=len({agent for _med, agent in nsaid_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        lithium_medication: str,
        lithium_agent: str,
        lithium_descriptor: str,
        nsaid_medication: str,
        nsaid_agent: str,
        nsaid_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY lithium × NSAID toxicity rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{lithium_medication}' contains {lithium_agent}, "
            f"{lithium_descriptor}, and is co-prescribed with '{nsaid_medication}' "
            f"({nsaid_agent}, {nsaid_descriptor}). NSAIDs can reduce renal "
            "lithium clearance and raise serum lithium concentrations, increasing "
            "lithium toxicity risk. Review urgently; consider lithium level and "
            "renal function monitoring, NSAID avoidance, or an analgesic "
            "alternative when clinically appropriate."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
