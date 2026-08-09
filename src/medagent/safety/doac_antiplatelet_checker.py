"""DOAC + antiplatelet bleed intensifier safety checker.

Direct oral anticoagulants (DOACs) combined with antiplatelet therapy increase
major bleeding risk beyond anticoagulation alone. This hazard is distinct from
the broader anticoagulation bleeding-risk panel, warfarin + NSAID intensifier
screening, and generic drug-drug interaction flagging.

This checker flags DOAC agents (apixaban, rivaroxaban, edoxaban, dabigatran)
co-prescribed with antiplatelet partners (aspirin, clopidogrel, prasugrel,
ticagrelor). Whole-token matching is used throughout. Findings are
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DoacAntiplateletRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical DOAC token -> short descriptor.
_DOAC_AGENTS: Final[dict[str, str]] = {
    "apixaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "rivaroxaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "edoxaban": "a direct oral anticoagulant (factor Xa inhibitor)",
    "dabigatran": "a direct oral anticoagulant (direct thrombin inhibitor)",
}

# Canonical antiplatelet token -> short descriptor.
_ANTIPLATELET_AGENTS: Final[dict[str, str]] = {
    "aspirin": "an antiplatelet agent that intensifies anticoagulation bleeding",
    "clopidogrel": "a P2Y12 inhibitor antiplatelet agent",
    "prasugrel": "a P2Y12 inhibitor antiplatelet agent",
    "ticagrelor": "a P2Y12 inhibitor antiplatelet agent",
}


class DoacAntiplateletChecker:
    """Flag DOACs co-prescribed with antiplatelet bleed intensifiers."""

    def check(self, medications: list[Medication]) -> list[DoacAntiplateletRisk]:
        """Return findings for each DOAC × antiplatelet pair.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`DoacAntiplateletRisk` per unique DOAC × antiplatelet
            agent pair across distinct medication entries, ordered by descending
            severity then DOAC medication, partner medication, and agents. An
            empty list is returned when DOACs or antiplatelets are absent.
        """
        doac_matches: list[tuple[Medication, str]] = []
        antiplatelet_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            doac_candidates = sorted(tokens & set(_DOAC_AGENTS))
            if doac_candidates:
                doac_matches.append((medication, doac_candidates[0]))

            antiplatelet_candidates = sorted(tokens & set(_ANTIPLATELET_AGENTS))
            if antiplatelet_candidates:
                antiplatelet_matches.append((medication, antiplatelet_candidates[0]))

        if not doac_matches or not antiplatelet_matches:
            logger.info("doac_antiplatelet_checked", findings=0)
            return []

        findings: list[DoacAntiplateletRisk] = []
        pair_keys_seen: set[tuple[str, str]] = set()

        for doac_med, doac_agent in doac_matches:
            doac_desc = _DOAC_AGENTS[doac_agent]
            for antiplatelet_med, antiplatelet_agent in antiplatelet_matches:
                pair_key = (doac_agent, antiplatelet_agent)
                if pair_key in pair_keys_seen:
                    continue
                pair_keys_seen.add(pair_key)
                antiplatelet_desc = _ANTIPLATELET_AGENTS[antiplatelet_agent]
                findings.append(
                    DoacAntiplateletRisk(
                        medication=doac_med.name,
                        agent=doac_agent,
                        partner_medication=antiplatelet_med.name,
                        partner_agent=antiplatelet_agent,
                        severity=Severity.HIGH,
                        rationale=self._build_rationale(
                            doac_medication=doac_med.name,
                            doac_agent=doac_agent,
                            doac_descriptor=doac_desc,
                            antiplatelet_medication=antiplatelet_med.name,
                            antiplatelet_agent=antiplatelet_agent,
                            antiplatelet_descriptor=antiplatelet_desc,
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
            "doac_antiplatelet_checked",
            findings=len(findings),
            doac_agents=len({agent for _med, agent in doac_matches}),
            antiplatelet_agents=len({agent for _med, agent in antiplatelet_matches}),
        )
        return findings

    @staticmethod
    def _build_rationale(
        *,
        doac_medication: str,
        doac_agent: str,
        doac_descriptor: str,
        antiplatelet_medication: str,
        antiplatelet_agent: str,
        antiplatelet_descriptor: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY DOAC × antiplatelet rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{doac_medication}' contains {doac_agent}, "
            f"{doac_descriptor}, and is co-prescribed with '{antiplatelet_medication}' "
            f"({antiplatelet_agent}, {antiplatelet_descriptor}). Concurrent DOAC "
            "anticoagulation with antiplatelet therapy intensifies major bleeding "
            "risk. Review urgently; confirm indication for dual therapy, duration, "
            "gastroprotection, and bleeding-risk mitigation when clinically "
            "appropriate."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
