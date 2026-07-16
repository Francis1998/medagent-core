"""Drug–food interaction safety checker.

A patient's active medication list and dietary context (grapefruit, dairy,
tyramine-rich foods, alcohol, and similar flags) can combine into clinically
significant interactions that neither a drug–drug interaction check nor an
allergy/duplicate-therapy check surfaces: the hazard is between a drug and a
*food or beverage exposure*, not another medication.

This checker matches medications and dietary flags to a conservative panel of
well-established pairs — for example grapefruit with simvastatin/atorvastatin,
dairy with tetracycline/ciprofloxacin, tyramine with MAOIs, and alcohol with
metronidazole/disulfiram — using whole-token matching (never loose substrings).
It is deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DrugFoodInteractionRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class _FoodInteraction:
    """A canonical drug–food interaction panel entry.

    Attributes:
        food_category: Canonical dietary category (e.g. ``grapefruit``).
        food_aliases: Whole-token aliases that identify the dietary flag.
        agents: Medication component tokens that interact with this food.
        severity: Severity assigned when the pair is present.
        rationale: Short clinical reason for the interaction.
    """

    __slots__ = ("agents", "food_aliases", "food_category", "rationale", "severity")

    def __init__(
        self,
        food_category: str,
        food_aliases: frozenset[str],
        agents: frozenset[str],
        severity: Severity,
        rationale: str,
    ) -> None:
        """Initialize a panel entry."""
        self.food_category = food_category
        self.food_aliases = food_aliases
        self.agents = agents
        self.severity = severity
        self.rationale = rationale


# Conservative, widely-cited drug–food pairs. Food aliases and drug agents are
# matched as whole tokens of the dietary flag / medication name.
_PANEL: Final[tuple[_FoodInteraction, ...]] = (
    _FoodInteraction(
        "grapefruit",
        frozenset({"grapefruit"}),
        frozenset({"simvastatin", "atorvastatin"}),
        Severity.HIGH,
        "grapefruit inhibits CYP3A4 and can raise statin exposure (myopathy risk)",
    ),
    _FoodInteraction(
        "dairy",
        frozenset({"dairy", "milk", "calcium"}),
        frozenset({"tetracycline", "doxycycline", "minocycline", "ciprofloxacin"}),
        Severity.MODERATE,
        "dairy/calcium chelates the antibiotic and reduces absorption",
    ),
    _FoodInteraction(
        "tyramine",
        frozenset({"tyramine"}),
        frozenset({"phenelzine", "tranylcypromine", "isocarboxazid"}),
        Severity.CRITICAL,
        "tyramine with an MAOI can precipitate a hypertensive crisis",
    ),
    _FoodInteraction(
        "alcohol",
        frozenset({"alcohol", "ethanol"}),
        frozenset({"metronidazole", "disulfiram"}),
        Severity.HIGH,
        "alcohol with this agent can cause a disulfiram-like reaction",
    ),
)


class DrugFoodInteractionChecker:
    """Flag interactions between medications and dietary exposures."""

    def check(
        self, medications: list[Medication], dietary_flags: list[str]
    ) -> list[DrugFoodInteractionRisk]:
        """Return drug–food interaction findings for medications and diet flags.

        Args:
            medications: Active patient medications.
            dietary_flags: Free-text dietary exposure flags (e.g. ``grapefruit``,
                ``dairy``, ``tyramine``, ``alcohol``).

        Returns:
            One :class:`DrugFoodInteractionRisk` per matching (medication, food)
            pair, ordered by descending severity then medication name. An empty
            list is returned when no panel pair is present.
        """
        flag_entries = [(flag, self._tokens(flag)) for flag in dietary_flags if flag.strip()]
        findings: list[DrugFoodInteractionRisk] = []
        for medication in medications:
            med_tokens = self._tokens(medication.name)
            if not med_tokens:
                continue
            for flag_text, flag_tokens in flag_entries:
                if not flag_tokens:
                    continue
                for entry in _PANEL:
                    if not (flag_tokens & entry.food_aliases):
                        continue
                    matched_agents = med_tokens & entry.agents
                    if not matched_agents:
                        continue
                    agent = sorted(matched_agents)[0]
                    findings.append(
                        DrugFoodInteractionRisk(
                            medication=medication.name,
                            agent=agent,
                            dietary_flag=flag_text,
                            food_category=entry.food_category,
                            severity=entry.severity,
                            rationale=(
                                f"Medication '{medication.name}' ({agent}) interacts with "
                                f"dietary flag '{flag_text}' ({entry.food_category}): "
                                f"{entry.rationale}."
                            ),
                        )
                    )
        findings.sort(
            key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication.lower())
        )
        logger.info("drug_food_interactions_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a name.

        Args:
            name: Medication or dietary-flag text (may contain separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
