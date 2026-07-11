"""Beers Criteria potentially-inappropriate-medication safety checker.

The American Geriatrics Society (AGS) Beers Criteria list medications whose
risk generally outweighs their benefit in adults aged 65 and older — for
example long-acting benzodiazepines (falls, prolonged sedation), tertiary
tricyclic antidepressants and first-generation antihistamines (strong
anticholinergic load), long-acting sulfonylureas (prolonged hypoglycaemia), and
skeletal muscle relaxants (sedation, anticholinergic effects). Unlike the
drug-drug interaction, drug-allergy, duplicate-therapy, pregnancy-safety,
QT-prolongation, anticholinergic-burden, and serotonin-syndrome checkers — which
key on drug pairs, combinations, or cumulative load — this hazard is an
*age-conditioned, single-agent* appropriateness judgement, so it is not surfaced
by the existing checkers.

This checker applies only to patients aged 65 and older; below that age (or when
age is unknown) it returns no findings. For an eligible patient it flags each
active medication that matches a Beers-listed agent, using whole-token matching
(never loose substrings). It is deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import BeersCriteriaRisk, Medication, Severity

logger = get_logger(__name__)

# The Beers Criteria apply to older adults; this is the standard age threshold.
_OLDER_ADULT_AGE_THRESHOLD: Final[int] = 65

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical Beers-listed agent token -> (category, severity, concern descriptor).
# Agents are matched as whole component tokens of a medication name.
_BEERS_AGENTS: dict[str, tuple[str, Severity, str]] = {
    # Long-acting benzodiazepines (falls, fractures, prolonged sedation).
    "diazepam": ("long-acting benzodiazepine", Severity.HIGH, "increased fall and fracture risk"),
    "chlordiazepoxide": (
        "long-acting benzodiazepine",
        Severity.HIGH,
        "increased fall and fracture risk",
    ),
    "clonazepam": ("benzodiazepine", Severity.HIGH, "increased fall and fracture risk"),
    "flurazepam": ("long-acting benzodiazepine", Severity.HIGH, "prolonged sedation and falls"),
    # Short/intermediate benzodiazepines (still Beers-listed in older adults).
    "alprazolam": ("benzodiazepine", Severity.HIGH, "increased fall and fracture risk"),
    "lorazepam": ("benzodiazepine", Severity.HIGH, "increased fall and fracture risk"),
    "temazepam": ("benzodiazepine", Severity.HIGH, "increased fall and fracture risk"),
    # Non-benzodiazepine "Z-drug" hypnotics.
    "zolpidem": ("nonbenzodiazepine hypnotic", Severity.MODERATE, "falls and next-day sedation"),
    "zaleplon": ("nonbenzodiazepine hypnotic", Severity.MODERATE, "falls and next-day sedation"),
    "eszopiclone": ("nonbenzodiazepine hypnotic", Severity.MODERATE, "falls and next-day sedation"),
    # First-generation (sedating, anticholinergic) antihistamines.
    "diphenhydramine": (
        "first-generation antihistamine",
        Severity.MODERATE,
        "anticholinergic load",
    ),
    "hydroxyzine": ("first-generation antihistamine", Severity.MODERATE, "anticholinergic load"),
    "chlorpheniramine": (
        "first-generation antihistamine",
        Severity.MODERATE,
        "anticholinergic load",
    ),
    "promethazine": ("first-generation antihistamine", Severity.MODERATE, "anticholinergic load"),
    # Tertiary tricyclic antidepressants (highly anticholinergic).
    "amitriptyline": (
        "tertiary tricyclic antidepressant",
        Severity.HIGH,
        "strong anticholinergic load",
    ),
    "imipramine": (
        "tertiary tricyclic antidepressant",
        Severity.HIGH,
        "strong anticholinergic load",
    ),
    "doxepin": ("tertiary tricyclic antidepressant", Severity.HIGH, "strong anticholinergic load"),
    # Skeletal muscle relaxants (sedation, anticholinergic, weakness).
    "cyclobenzaprine": (
        "skeletal muscle relaxant",
        Severity.MODERATE,
        "sedation and anticholinergic effects",
    ),
    "carisoprodol": ("skeletal muscle relaxant", Severity.MODERATE, "sedation and dependence"),
    "methocarbamol": ("skeletal muscle relaxant", Severity.MODERATE, "sedation and falls"),
    # Long-acting sulfonylureas (prolonged, severe hypoglycaemia).
    "glyburide": ("long-acting sulfonylurea", Severity.HIGH, "prolonged hypoglycaemia"),
    "glibenclamide": ("long-acting sulfonylurea", Severity.HIGH, "prolonged hypoglycaemia"),
    "chlorpropamide": ("long-acting sulfonylurea", Severity.HIGH, "prolonged hypoglycaemia"),
    # Barbiturates (high dependence, sedation).
    "phenobarbital": ("barbiturate", Severity.HIGH, "high dependence and overdose risk"),
    "butalbital": ("barbiturate", Severity.HIGH, "high dependence and overdose risk"),
    # NSAIDs with a poor geriatric risk profile.
    "indomethacin": ("NSAID", Severity.MODERATE, "GI bleeding and CNS effects"),
    "ketorolac": ("NSAID", Severity.HIGH, "GI bleeding and acute kidney injury"),
    # Peripheral alpha-1 blockers for hypertension (orthostatic hypotension).
    "doxazosin": ("peripheral alpha-1 blocker", Severity.MODERATE, "orthostatic hypotension"),
    "prazosin": ("peripheral alpha-1 blocker", Severity.MODERATE, "orthostatic hypotension"),
    "terazosin": ("peripheral alpha-1 blocker", Severity.MODERATE, "orthostatic hypotension"),
}


class BeersCriteriaChecker:
    """Flag Beers Criteria potentially inappropriate medications in older adults."""

    def check(self, medications: list[Medication], age: int | None) -> list[BeersCriteriaRisk]:
        """Return Beers Criteria findings for an older adult's active medications.

        The Beers Criteria apply only to adults aged 65 and older, so no finding
        is returned for a younger patient or when the age is unknown. For an
        eligible patient, each active medication matching a Beers-listed agent
        yields one finding.

        Args:
            medications: Active patient medications.
            age: Patient age in years, or None when unknown.

        Returns:
            One :class:`BeersCriteriaRisk` per matching medication, ordered by
            descending severity then medication name. When a medication matches
            more than one Beers agent, the alphabetically first agent is used.
            An empty list is returned for patients under 65, unknown age, or when
            no medication is Beers-listed.
        """
        if age is None or age < _OLDER_ADULT_AGE_THRESHOLD:
            logger.info("beers_criteria_checked", findings=0, eligible=False)
            return []

        findings: list[BeersCriteriaRisk] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            matched_agents = sorted(tokens & set(_BEERS_AGENTS))
            if not matched_agents:
                continue
            agent = matched_agents[0]
            category, severity, concern = _BEERS_AGENTS[agent]
            rationale = (
                f"Medication '{medication.name}' contains {agent}, a {category} on the AGS Beers "
                f"Criteria of potentially inappropriate medications for adults aged "
                f"{_OLDER_ADULT_AGE_THRESHOLD} and older (patient age {age}). The primary concern "
                f"is {concern}. Consider a safer alternative or review the indication."
            )
            findings.append(
                BeersCriteriaRisk(
                    medication=medication.name,
                    agent=agent,
                    beers_category=category,
                    severity=severity,
                    rationale=rationale,
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("beers_criteria_checked", findings=len(findings), eligible=True)
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
