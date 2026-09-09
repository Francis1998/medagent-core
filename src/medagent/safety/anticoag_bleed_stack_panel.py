"""Anticoag bleed stack panel - aggregate multi-agent hemorrhage load.

The existing :class:`~medagent.safety.anticoag_bleeding_checker.AnticoagBleedingChecker`
emits **pairwise** anticoagulant × augmenter findings, and
:class:`~medagent.safety.doac_nsaid_checker.DoacNsaidChecker` covers named
DOAC+NSAID pairs. Neither produces a single panel-level aggregate that
summarises multi-class bleed stacks (anticoagulant + antiplatelet + NSAID)
across the medication list.

This panel fills that gap: it aggregates matching agents into advisory
:class:`~medagent.models.AnticoagBleedStackRisk` findings (triple stack,
anticoag+antiplatelet, anticoag+NSAID, dual antiplatelet on anticoag, multi
anticoagulant). Findings are RESEARCH USE ONLY and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AnticoagBleedStackRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_ANTICOAGULANTS: Final[frozenset[str]] = frozenset(
    {
        "warfarin",
        "apixaban",
        "rivaroxaban",
        "dabigatran",
        "edoxaban",
        "enoxaparin",
        "heparin",
    }
)

_ANTIPLATELETS: Final[frozenset[str]] = frozenset(
    {
        "aspirin",
        "clopidogrel",
        "prasugrel",
        "ticagrelor",
    }
)

_NSAIDS: Final[frozenset[str]] = frozenset(
    {
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "ketorolac",
        "meloxicam",
        "celecoxib",
        "indomethacin",
    }
)


class AnticoagBleedStackPanel:
    """Aggregate anticoag + antiplatelet + NSAID combinations into panel findings."""

    def check(self, medications: list[Medication]) -> list[AnticoagBleedStackRisk]:
        """Return aggregate bleed-stack findings for the active medication list.

        Args:
            medications: Active patient medications.

        Returns:
            Zero or more :class:`AnticoagBleedStackRisk` findings summarising
            multi-agent bleed stacks. Distinct from pairwise
            :class:`AnticoagBleedingChecker` and :class:`DoacNsaidChecker`
            findings.
        """
        anticoags: list[tuple[str, str]] = []
        antiplatelets: list[tuple[str, str]] = []
        nsaids: list[tuple[str, str]] = []
        seen_ac: set[str] = set()
        seen_ap: set[str] = set()
        seen_nsaid: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _ANTICOAGULANTS):
                if agent in seen_ac:
                    continue
                anticoags.append((medication.name, agent))
                seen_ac.add(agent)
            for agent in sorted(tokens & _ANTIPLATELETS):
                if agent in seen_ap:
                    continue
                antiplatelets.append((medication.name, agent))
                seen_ap.add(agent)
            for agent in sorted(tokens & _NSAIDS):
                if agent in seen_nsaid:
                    continue
                nsaids.append((medication.name, agent))
                seen_nsaid.add(agent)

        ac_agents = [agent for _med, agent in anticoags]
        ap_agents = [agent for _med, agent in antiplatelets]
        nsaid_agents = [agent for _med, agent in nsaids]
        all_meds = sorted(
            {med for med, _agent in anticoags + antiplatelets + nsaids},
            key=str.casefold,
        )

        if not ac_agents:
            logger.info("anticoag_bleed_stack_panel_checked", findings=0)
            return []

        findings: list[AnticoagBleedStackRisk] = []

        # Triple stack: anticoag + antiplatelet + NSAID
        if ac_agents and ap_agents and nsaid_agents:
            findings.append(
                AnticoagBleedStackRisk(
                    finding_kind="triple_stack",
                    anticoagulants=ac_agents,
                    antiplatelets=ap_agents,
                    nsaids=nsaid_agents,
                    medication_names=all_meds,
                    stack_size=len(ac_agents) + len(ap_agents) + len(nsaid_agents),
                    severity=Severity.CRITICAL,
                    rationale=(
                        "RESEARCH USE ONLY: Anticoag bleed stack panel detected a "
                        "triple stack — anticoagulants "
                        f"({', '.join(ac_agents)}), antiplatelets "
                        f"({', '.join(ap_agents)}), and NSAIDs "
                        f"({', '.join(nsaid_agents)}). Aggregate multi-class bleed "
                        "load is distinct from pairwise AnticoagBleedingChecker / "
                        "DoacNsaidChecker findings. Not a prescription. Confirm "
                        "with a qualified clinician; prefer GPT-5.5 / Claude "
                        "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        # Dual antiplatelet on anticoagulant
        if ac_agents and len(ap_agents) >= 2:
            findings.append(
                AnticoagBleedStackRisk(
                    finding_kind="dual_antiplatelet_on_anticoag",
                    anticoagulants=ac_agents,
                    antiplatelets=ap_agents,
                    nsaids=nsaid_agents,
                    medication_names=all_meds,
                    stack_size=len(ac_agents) + len(ap_agents),
                    severity=Severity.CRITICAL,
                    rationale=(
                        "RESEARCH USE ONLY: Dual antiplatelet therapy on "
                        f"anticoagulant(s) {', '.join(ac_agents)} with "
                        f"antiplatelets {', '.join(ap_agents)}. Panel-level DAPT "
                        "+ anticoag stack distinct from pairwise anticoag "
                        "bleeding checker. Confirm with a qualified clinician; "
                        "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        # Anticoag + antiplatelet (when not already covered only by dual AP case
        # — still emit when exactly one AP, or always as class stack summary)
        if ac_agents and ap_agents and len(ap_agents) == 1:
            findings.append(
                AnticoagBleedStackRisk(
                    finding_kind="anticoag_antiplatelet_stack",
                    anticoagulants=ac_agents,
                    antiplatelets=ap_agents,
                    nsaids=nsaid_agents,
                    medication_names=all_meds,
                    stack_size=len(ac_agents) + len(ap_agents),
                    severity=Severity.CRITICAL,
                    rationale=(
                        "RESEARCH USE ONLY: Anticoagulant + antiplatelet stack — "
                        f"{', '.join(ac_agents)} with {', '.join(ap_agents)}. "
                        "Aggregate panel distinct from pairwise "
                        "AnticoagBleedingChecker pairs. Confirm with a qualified "
                        "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini "
                        "3.x / Kimi K2."
                    ),
                )
            )

        # Anticoag + NSAID
        if ac_agents and nsaid_agents:
            findings.append(
                AnticoagBleedStackRisk(
                    finding_kind="anticoag_nsaid_stack",
                    anticoagulants=ac_agents,
                    antiplatelets=ap_agents,
                    nsaids=nsaid_agents,
                    medication_names=all_meds,
                    stack_size=len(ac_agents) + len(nsaid_agents),
                    severity=Severity.HIGH,
                    rationale=(
                        "RESEARCH USE ONLY: Anticoagulant + NSAID stack — "
                        f"{', '.join(ac_agents)} with {', '.join(nsaid_agents)}. "
                        "Aggregate panel distinct from pairwise DoacNsaidChecker / "
                        "AnticoagBleedingChecker. Confirm with a qualified "
                        "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini "
                        "3.x / Kimi K2."
                    ),
                )
            )

        # Multiple anticoagulants
        if len(ac_agents) >= 2:
            findings.append(
                AnticoagBleedStackRisk(
                    finding_kind="multi_anticoag_stack",
                    anticoagulants=ac_agents,
                    antiplatelets=ap_agents,
                    nsaids=nsaid_agents,
                    medication_names=[med for med, _agent in anticoags],
                    stack_size=len(ac_agents),
                    severity=Severity.HIGH,
                    rationale=(
                        "RESEARCH USE ONLY: Multiple anticoagulant stack — "
                        f"{', '.join(ac_agents)}. Aggregate multi-anticoagulant "
                        "panel distinct from pairwise bleeding-augmenter "
                        "checkers. Confirm with a qualified clinician; prefer "
                        "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        findings.sort(
            key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind)
        )
        logger.info("anticoag_bleed_stack_panel_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
