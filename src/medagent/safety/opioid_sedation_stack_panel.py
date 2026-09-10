"""Opioid sedation stack panel - aggregate opioid + benzo + gabapentinoid load.

The existing :class:`~medagent.safety.opioid_benzo_checker.OpioidBenzoChecker`
and :class:`~medagent.safety.opioid_med_checker.OpioidMedChecker` emit pairwise
or single-agent findings. Neither produces a panel-level aggregate that
summarises multi-class sedation stacks across the medication list.

This panel fills that gap: it aggregates matching agents into advisory
:class:`~medagent.models.OpioidSedationStackRisk` findings. Findings are
RESEARCH USE ONLY and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, OpioidSedationStackRisk, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_OPIOIDS: Final[frozenset[str]] = frozenset(
    {
        "morphine",
        "oxycodone",
        "hydrocodone",
        "hydromorphone",
        "fentanyl",
        "codeine",
        "tramadol",
        "methadone",
        "oxymorphone",
        "buprenorphine",
    }
)

_BENZOS: Final[frozenset[str]] = frozenset(
    {
        "lorazepam",
        "alprazolam",
        "clonazepam",
        "diazepam",
        "temazepam",
        "midazolam",
        "oxazepam",
        "chlordiazepoxide",
    }
)

_GABAPENTINOIDS: Final[frozenset[str]] = frozenset(
    {
        "gabapentin",
        "pregabalin",
    }
)


class OpioidSedationStackPanel:
    """Aggregate opioid + benzo + gabapentinoid combinations into panel findings."""

    def check(self, medications: list[Medication]) -> list[OpioidSedationStackRisk]:
        """Return aggregate sedation-stack findings for the active medication list.

        Args:
            medications: Active patient medications.

        Returns:
            Zero or more :class:`OpioidSedationStackRisk` findings. Distinct from
            pairwise OpioidBenzoChecker / OpioidMedChecker. Never modifies meds.
        """
        opioids: list[tuple[str, str]] = []
        benzos: list[tuple[str, str]] = []
        gabas: list[tuple[str, str]] = []
        seen_o: set[str] = set()
        seen_b: set[str] = set()
        seen_g: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _OPIOIDS):
                if agent in seen_o:
                    continue
                opioids.append((medication.name, agent))
                seen_o.add(agent)
            for agent in sorted(tokens & _BENZOS):
                if agent in seen_b:
                    continue
                benzos.append((medication.name, agent))
                seen_b.add(agent)
            for agent in sorted(tokens & _GABAPENTINOIDS):
                if agent in seen_g:
                    continue
                gabas.append((medication.name, agent))
                seen_g.add(agent)

        o_agents = [a for _m, a in opioids]
        b_agents = [a for _m, a in benzos]
        g_agents = [a for _m, a in gabas]
        all_meds = sorted(
            {m for m, _a in opioids + benzos + gabas},
            key=str.casefold,
        )

        if not o_agents and not (b_agents and g_agents):
            logger.info("opioid_sedation_stack_panel_checked", findings=0)
            return []

        findings: list[OpioidSedationStackRisk] = []

        def _add(kind: str, severity: Severity, stack_size: int, rationale: str) -> None:
            findings.append(
                OpioidSedationStackRisk(
                    finding_kind=kind,
                    opioids=o_agents,
                    benzodiazepines=b_agents,
                    gabapentinoids=g_agents,
                    medication_names=all_meds,
                    stack_size=stack_size,
                    severity=severity,
                    rationale=rationale,
                )
            )

        if o_agents and b_agents and g_agents:
            _add(
                "triple_sedation_stack",
                Severity.CRITICAL,
                len(o_agents) + len(b_agents) + len(g_agents),
                (
                    "RESEARCH USE ONLY: Triple sedation stack — opioids "
                    f"{', '.join(o_agents)}, benzodiazepines {', '.join(b_agents)}, "
                    f"gabapentinoids {', '.join(g_agents)}. Aggregate panel distinct "
                    "from pairwise OpioidBenzoChecker. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / "
                    "Kimi K2."
                ),
            )
        if o_agents and b_agents:
            _add(
                "opioid_benzo_stack",
                Severity.CRITICAL if g_agents else Severity.HIGH,
                len(o_agents) + len(b_agents),
                (
                    "RESEARCH USE ONLY: Opioid + benzodiazepine panel stack — "
                    f"{', '.join(o_agents)} with {', '.join(b_agents)}. Panel-level "
                    "aggregate distinct from pairwise OpioidBenzoChecker. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 "
                    "/ Gemini 3.x / Kimi K2."
                ),
            )
        if o_agents and g_agents:
            _add(
                "opioid_gabapentinoid_stack",
                Severity.HIGH,
                len(o_agents) + len(g_agents),
                (
                    "RESEARCH USE ONLY: Opioid + gabapentinoid panel stack — "
                    f"{', '.join(o_agents)} with {', '.join(g_agents)}. Aggregate "
                    "panel for respiratory-depression additive risk. Confirm with "
                    "a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )
        if b_agents and g_agents and not o_agents:
            _add(
                "benzo_gabapentinoid_stack",
                Severity.MODERATE,
                len(b_agents) + len(g_agents),
                (
                    "RESEARCH USE ONLY: Benzodiazepine + gabapentinoid panel stack "
                    f"— {', '.join(b_agents)} with {', '.join(g_agents)}. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 "
                    "/ Gemini 3.x / Kimi K2."
                ),
            )
        if len(o_agents) >= 2:
            _add(
                "multi_opioid_stack",
                Severity.HIGH,
                len(o_agents),
                (
                    "RESEARCH USE ONLY: Multi-opioid panel stack — "
                    f"{', '.join(o_agents)}. Aggregate panel distinct from single "
                    "OpioidMedChecker findings. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.finding_kind))
        logger.info("opioid_sedation_stack_panel_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
