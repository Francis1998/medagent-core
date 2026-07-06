"""Duplicate-therapy detector.

A patient's active medication list can contain more than one agent from the same
therapeutic class — for example two NSAIDs, two SSRIs, or two anticoagulants.
Such duplication is a well-recognized source of avoidable harm (additive
toxicity, bleeding, serotonin syndrome) that a drug-drug *interaction* check does
not necessarily surface, because the drugs are not interacting so much as being
redundant.

This checker groups the active medications by therapeutic class using
whole-token matching (never loose substrings) and flags any class that contains
two or more *distinct* agents. Listing the same drug twice is not a therapeutic
duplication and is deliberately not flagged. It is deterministic and RESEARCH USE
ONLY, complementing the drug-drug interaction and drug-allergy checkers.
"""

from __future__ import annotations

import re

from medagent.logging_config import get_logger
from medagent.models import DuplicateTherapy, Medication, Severity

logger = get_logger(__name__)

# Therapeutic classes whose intra-class duplication is clinically significant.
# Members are matched as whole component tokens of a medication name.
_THERAPEUTIC_CLASSES: list[tuple[str, Severity, frozenset[str]]] = [
    (
        "anticoagulants",
        Severity.CRITICAL,
        frozenset(
            {
                "warfarin",
                "apixaban",
                "rivaroxaban",
                "dabigatran",
                "edoxaban",
                "heparin",
                "enoxaparin",
            }
        ),
    ),
    (
        "ssris",
        Severity.HIGH,
        frozenset(
            {
                "fluoxetine",
                "sertraline",
                "paroxetine",
                "citalopram",
                "escitalopram",
                "fluvoxamine",
            }
        ),
    ),
    (
        "benzodiazepines",
        Severity.HIGH,
        frozenset(
            {
                "diazepam",
                "lorazepam",
                "alprazolam",
                "clonazepam",
                "temazepam",
                "midazolam",
            }
        ),
    ),
    (
        "opioids",
        Severity.HIGH,
        frozenset(
            {
                "morphine",
                "oxycodone",
                "hydrocodone",
                "fentanyl",
                "codeine",
                "tramadol",
                "hydromorphone",
            }
        ),
    ),
    (
        "nsaids",
        Severity.MODERATE,
        frozenset(
            {
                "ibuprofen",
                "naproxen",
                "aspirin",
                "ketorolac",
                "diclofenac",
                "celecoxib",
                "meloxicam",
                "indomethacin",
            }
        ),
    ),
    (
        "ace_inhibitors",
        Severity.MODERATE,
        frozenset(
            {
                "lisinopril",
                "enalapril",
                "ramipril",
                "captopril",
                "benazepril",
                "perindopril",
            }
        ),
    ),
    (
        "statins",
        Severity.MODERATE,
        frozenset(
            {
                "atorvastatin",
                "simvastatin",
                "rosuvastatin",
                "pravastatin",
                "lovastatin",
                "pitavastatin",
            }
        ),
    ),
    (
        "proton_pump_inhibitors",
        Severity.LOW,
        frozenset(
            {
                "omeprazole",
                "esomeprazole",
                "lansoprazole",
                "pantoprazole",
                "rabeprazole",
                "dexlansoprazole",
            }
        ),
    ),
]


class DuplicateTherapyChecker:
    """Flag active medications that duplicate a therapeutic class."""

    def check(self, medications: list[Medication]) -> list[DuplicateTherapy]:
        """Return one finding per therapeutic class with duplicated agents.

        Distinct agents are keyed by the canonical member token they match, so
        the same drug listed twice (or a brand/generic pair for one agent) does
        not count as a duplication; only two or more different agents in one
        class do.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`DuplicateTherapy` per class holding ≥2 distinct agents,
            ordered by descending severity then class name.
        """
        # class name -> {canonical member token -> representative display name}
        class_members: dict[str, dict[str, str]] = {}
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            for class_name, _severity, members in _THERAPEUTIC_CLASSES:
                matched = tokens & members
                for member in matched:
                    class_members.setdefault(class_name, {}).setdefault(member, medication.name)

        severity_by_class = {name: severity for name, severity, _ in _THERAPEUTIC_CLASSES}
        findings: list[DuplicateTherapy] = []
        for class_name, matched_members in class_members.items():
            if len(matched_members) < 2:
                continue
            agents = sorted(matched_members.values())
            severity = severity_by_class[class_name]
            findings.append(
                DuplicateTherapy(
                    therapeutic_class=class_name,
                    medications=agents,
                    severity=severity,
                    rationale=(
                        f"Active medications {', '.join(agents)} are all {class_name}; "
                        "duplicate therapy within one class raises additive-toxicity risk."
                    ),
                )
            )

        findings.sort(
            key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.therapeutic_class)
        )
        logger.info("duplicate_therapy_checked", findings=len(findings))
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


# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}
