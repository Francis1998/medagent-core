"""Geriatric deprescribing-opportunity safety checker.

Deprescribing reviews ask a different question than Beers or STOPP/START:
instead of only asking whether an active medication is formally inappropriate
or omitted, they ask whether a chronic medication is a reasonable candidate for
supervised dose reduction, step-down, or substitution in an older adult. Common
educational examples include long-term proton-pump inhibitors without a clear
ongoing indication, sedative-hypnotics used for insomnia, first-generation
antihistamines used chronically, and scheduled NSAIDs.

This checker applies only to patients aged 65 and older; below that age (or when
age is unknown) it returns no findings. It uses a conservative, curated
RESEARCH USE ONLY catalog with whole-token medication matching and optional
free-text indication matching for PPI suppression. Findings are advisory and
never modify a medication list.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import GeriatricDeprescribingRisk, Medication, Severity

logger = get_logger(__name__)

# Deprescribing reviews commonly use the same older-adult threshold as Beers and
# STOPP/START, but the output is framed as a review/taper opportunity.
_OLDER_ADULT_AGE_THRESHOLD: Final[int] = 65

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_LONG_TERM_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "bid",
        "chronic",
        "daily",
        "maintenance",
        "nightly",
        "qday",
        "qd",
        "qid",
        "scheduled",
        "tid",
    }
)

_LONG_TERM_PHRASES: Final[tuple[str, ...]] = (
    "every day",
    "long term",
    "long-term",
    "once daily",
    "twice daily",
)

_PPI_INDICATION_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "barrett",
        "barrett esophagus",
        "barrett oesophagus",
        "erosive esophagitis",
        "erosive oesophagitis",
        "gastroprotection",
        "gi bleed",
        "gi bleeding",
        "gib",
        "peptic ulcer",
        "severe gerd",
        "upper gi bleed",
        "zollinger ellison",
    }
)


class _DeprescribingRule:
    """A curated deprescribing opportunity entry.

    Attributes:
        agents: Medication tokens that trigger this deprescribing rule.
        category: Human-readable deprescribing opportunity category.
        severity: Severity assigned when the rule fires.
        suggested_action: Research-only review action.
        concern: Short clinical concern included in the rationale.
        taper_candidate: Whether chronic use generally warrants taper/step-down.
        requires_long_term_signal: Whether the medication needs a chronic-use
            signal before it is flagged.
        suppress_with_indication: Whether matching indications suppress the rule.
    """

    __slots__ = (
        "agents",
        "category",
        "concern",
        "requires_long_term_signal",
        "severity",
        "suggested_action",
        "suppress_with_indication",
        "taper_candidate",
    )

    def __init__(
        self,
        agents: frozenset[str],
        category: str,
        severity: Severity,
        suggested_action: str,
        concern: str,
        *,
        taper_candidate: bool,
        requires_long_term_signal: bool = False,
        suppress_with_indication: bool = False,
    ) -> None:
        """Initialize a deprescribing rule."""
        self.agents = agents
        self.category = category
        self.severity = severity
        self.suggested_action = suggested_action
        self.concern = concern
        self.taper_candidate = taper_candidate
        self.requires_long_term_signal = requires_long_term_signal
        self.suppress_with_indication = suppress_with_indication


_DEPRESCRIBING_RULES: Final[tuple[_DeprescribingRule, ...]] = (
    _DeprescribingRule(
        frozenset(
            {
                "dexlansoprazole",
                "esomeprazole",
                "lansoprazole",
                "omeprazole",
                "pantoprazole",
                "rabeprazole",
            }
        ),
        "long-term PPI without clear ongoing indication",
        Severity.LOW,
        "review indication and consider step-down, dose reduction, or supervised taper",
        "long-term PPI exposure may be continued after the original indication has resolved",
        taper_candidate=True,
        requires_long_term_signal=True,
        suppress_with_indication=True,
    ),
    _DeprescribingRule(
        frozenset({"eszopiclone", "zaleplon", "zolpidem"}),
        "sedative-hypnotic deprescribing candidate",
        Severity.MODERATE,
        "review insomnia indication and consider gradual taper with non-drug sleep strategies",
        "sedative-hypnotics can contribute to falls, confusion, and next-day impairment",
        taper_candidate=True,
    ),
    _DeprescribingRule(
        frozenset({"chlorpheniramine", "diphenhydramine", "doxylamine", "hydroxyzine"}),
        "first-generation antihistamine deprescribing candidate",
        Severity.MODERATE,
        "review need and consider non-sedating antihistamine or non-drug alternative",
        "first-generation antihistamines can add sedating and anticholinergic burden",
        taper_candidate=False,
    ),
    _DeprescribingRule(
        frozenset({"diclofenac", "ibuprofen", "indomethacin", "meloxicam", "naproxen"}),
        "chronic NSAID deprescribing candidate",
        Severity.MODERATE,
        "review chronic pain plan and consider dose reduction, topical therapy, or alternatives",
        "scheduled NSAID exposure can increase gastrointestinal, renal, and cardiovascular risk",
        taper_candidate=False,
        requires_long_term_signal=True,
    ),
)


class GeriatricDeprescribingChecker:
    """Flag geriatric deprescribing opportunities in older adults."""

    def check(
        self,
        medications: list[Medication],
        age: int | None,
        indications: list[str] | None = None,
    ) -> list[GeriatricDeprescribingRisk]:
        """Return deprescribing-opportunity findings for an older adult.

        Args:
            medications: Active patient medications.
            age: Patient age in years, or None when unknown.
            indications: Optional free-text diagnoses / reasons for therapy.
                These only suppress long-term PPI findings when a protective
                indication such as Barrett esophagus or GI bleed is documented.

        Returns:
            One :class:`GeriatricDeprescribingRisk` per matching medication,
            ordered by descending severity then medication name. An empty list is
            returned for patients under 65, unknown age, or when no curated
            deprescribing opportunity matches.
        """
        if age is None or age < _OLDER_ADULT_AGE_THRESHOLD:
            logger.info("geriatric_deprescribing_checked", findings=0, eligible=False)
            return []

        indication_blob = self._indication_blob(indications or [])
        findings: list[GeriatricDeprescribingRisk] = []
        for medication in medications:
            medication_text = self._medication_text(medication)
            tokens = self._tokens(medication_text)
            matched = sorted(
                self._matching_rules(tokens, medication_text, indication_blob),
                key=lambda item: (-_SEVERITY_RANK[item[1].severity], item[0]),
            )
            if not matched:
                continue

            agent, rule = matched[0]
            findings.append(
                GeriatricDeprescribingRisk(
                    medication=medication.name,
                    agent=agent,
                    deprescribing_category=rule.category,
                    suggested_action=rule.suggested_action,
                    taper_candidate=rule.taper_candidate,
                    severity=rule.severity,
                    rationale=(
                        "RESEARCH USE ONLY: "
                        f"Medication '{medication.name}' contains {agent}, which matches the "
                        f"geriatric deprescribing category '{rule.category}' for adults aged "
                        f"{_OLDER_ADULT_AGE_THRESHOLD} and older (patient age {age}). "
                        f"Concern: {rule.concern}. Suggested review action: "
                        f"{rule.suggested_action}. Findings are educational and require "
                        "qualified clinician review before any medication change."
                    ),
                )
            )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication,
                finding.agent,
            )
        )
        logger.info("geriatric_deprescribing_checked", findings=len(findings), eligible=True)
        return findings

    def _matching_rules(
        self,
        tokens: set[str],
        medication_text: str,
        indication_blob: str,
    ) -> list[tuple[str, _DeprescribingRule]]:
        """Return matched ``(agent, rule)`` pairs after rule-specific gates."""
        matches: list[tuple[str, _DeprescribingRule]] = []
        for rule in _DEPRESCRIBING_RULES:
            if rule.requires_long_term_signal and not self._has_long_term_signal(
                tokens, medication_text
            ):
                continue
            if rule.suppress_with_indication and self._aliases_match(
                indication_blob, _PPI_INDICATION_ALIASES
            ):
                continue
            for agent in sorted(tokens & rule.agents):
                matches.append((agent, rule))
        return matches

    @staticmethod
    def _medication_text(medication: Medication) -> str:
        """Return searchable medication text including dose/frequency metadata."""
        return " ".join(
            value
            for value in (
                medication.name,
                medication.dosage,
                medication.frequency,
                medication.route,
            )
            if value
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        """Return lowercase alphanumeric component tokens from free text."""
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def _indication_blob(indications: list[str]) -> str:
        """Join free-text indications into a lowercase searchable blob."""
        return " ".join(indications).lower()

    @staticmethod
    def _has_long_term_signal(tokens: set[str], text: str) -> bool:
        """Return True when medication text suggests scheduled/chronic use."""
        if tokens & _LONG_TERM_TOKENS:
            return True
        normalized_text = text.lower().replace("-", " ")
        return any(phrase.replace("-", " ") in normalized_text for phrase in _LONG_TERM_PHRASES)

    @staticmethod
    def _aliases_match(blob: str, aliases: frozenset[str]) -> bool:
        """Return True when any alias matches as a whole token or phrase."""
        if not blob or not aliases:
            return False
        tokens = set(re.findall(r"[a-z0-9]+", blob))
        for alias in aliases:
            alias_l = alias.lower()
            if " " in alias_l or "-" in alias_l:
                if alias_l in blob:
                    return True
                continue
            if alias_l in tokens:
                return True
        return False
