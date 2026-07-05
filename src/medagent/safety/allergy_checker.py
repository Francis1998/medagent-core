"""Drug–allergy conflict checker.

A patient's documented allergies and their active medication list are both
carried on ``FHIRPatientContext``, but nothing cross-checks them. This module
flags two failure modes that cause real harm:

1. **Direct** conflicts — a medication that is (or contains) a substance the
   patient is documented as allergic to.
2. **Cross-reactivity** conflicts — a medication in the same drug class as an
   allergen, where class-level cross-reactivity is well documented (for example
   the penicillins, or the sulfonamide antibiotics).

The checker is deliberately conservative and deterministic: it matches on
whole-word/component tokens (never loose substrings) and only within
well-established classes, so it complements — and never replaces — the existing
drug-drug interaction checker. It is RESEARCH USE ONLY, like the rest of the
system, and does not model inter-class cross-reactivity (e.g. penicillin ↔
cephalosporin) to avoid false alarms.
"""

from __future__ import annotations

import re

from medagent.logging_config import get_logger
from medagent.models import AllergyConflict, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to pick the worst shared class deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Well-established drug classes with clinically significant intra-class allergy
# cross-reactivity. Members are matched as whole component tokens.
_CROSS_REACTIVITY_CLASSES: list[tuple[str, Severity, frozenset[str]]] = [
    (
        "penicillins",
        Severity.HIGH,
        frozenset(
            {
                "penicillin",
                "amoxicillin",
                "ampicillin",
                "piperacillin",
                "dicloxacillin",
                "nafcillin",
                "oxacillin",
                "augmentin",
            }
        ),
    ),
    (
        "cephalosporins",
        Severity.MODERATE,
        frozenset(
            {
                "cephalexin",
                "cefazolin",
                "ceftriaxone",
                "cefuroxime",
                "cefdinir",
                "cefepime",
                "cefixime",
            }
        ),
    ),
    (
        "sulfonamides",
        Severity.HIGH,
        frozenset(
            {"sulfamethoxazole", "sulfadiazine", "sulfasalazine", "bactrim", "cotrimoxazole"}
        ),
    ),
    (
        "nsaids",
        Severity.MODERATE,
        frozenset({"ibuprofen", "naproxen", "aspirin", "ketorolac", "diclofenac", "celecoxib"}),
    ),
]


class AllergyChecker:
    """Flag conflicts between medications and documented patient allergies."""

    def check(self, medications: list[Medication], allergies: list[str]) -> list[AllergyConflict]:
        """Return conflicts between medications and documented allergies.

        Args:
            medications: Active patient medications.
            allergies: Documented allergy substance names (free text).

        Returns:
            One :class:`AllergyConflict` per (medication, allergy) conflict. A
            direct match takes precedence over a cross-reactivity match for the
            same pair.
        """
        allergy_tokens = [
            (allergy, self._tokens(allergy)) for allergy in allergies if allergy.strip()
        ]
        conflicts: list[AllergyConflict] = []
        for medication in medications:
            med_tokens = self._tokens(medication.name)
            if not med_tokens:
                continue
            med_classes = self._classes_for(med_tokens)
            for allergy_text, allergy_toks in allergy_tokens:
                if not allergy_toks:
                    continue
                if self._is_direct(med_tokens, allergy_toks):
                    conflicts.append(
                        AllergyConflict(
                            medication=medication.name,
                            allergy=allergy_text,
                            match_type="direct",
                            severity=Severity.HIGH,
                            rationale=(
                                f"Medication '{medication.name}' matches the documented "
                                f"allergy '{allergy_text}'."
                            ),
                        )
                    )
                    continue
                shared_class = self._shared_class(med_classes, self._classes_for(allergy_toks))
                if shared_class is not None:
                    class_name, severity = shared_class
                    conflicts.append(
                        AllergyConflict(
                            medication=medication.name,
                            allergy=allergy_text,
                            match_type="cross_reactivity",
                            drug_class=class_name,
                            severity=severity,
                            rationale=(
                                f"Medication '{medication.name}' and allergy "
                                f"'{allergy_text}' are both {class_name}; documented "
                                "intra-class cross-reactivity."
                            ),
                        )
                    )
        logger.info("allergy_conflicts_checked", conflicts=len(conflicts))
        return conflicts

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a drug/allergy name.

        Args:
            name: Drug or allergy name (may contain brand/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))

    @staticmethod
    def _is_direct(med_tokens: set[str], allergy_tokens: set[str]) -> bool:
        """Report a direct match when either name's tokens contain the other's.

        Args:
            med_tokens: Tokens of the medication name.
            allergy_tokens: Tokens of the allergy name.

        Returns:
            True when one token set is a subset of the other (e.g. allergy
            ``penicillin`` vs medication ``penicillin v potassium``).
        """
        return allergy_tokens <= med_tokens or med_tokens <= allergy_tokens

    @staticmethod
    def _classes_for(tokens: set[str]) -> set[str]:
        """Return the names of cross-reactivity classes matched by tokens.

        Args:
            tokens: Component tokens of a drug/allergy name.

        Returns:
            Set of matched class names.
        """
        return {
            class_name
            for class_name, _severity, members in _CROSS_REACTIVITY_CLASSES
            if tokens & members
        }

    @staticmethod
    def _shared_class(
        med_classes: set[str], allergy_classes: set[str]
    ) -> tuple[str, Severity] | None:
        """Return the highest-severity class shared by medication and allergy.

        Args:
            med_classes: Classes matched by the medication.
            allergy_classes: Classes matched by the allergy.

        Returns:
            ``(class_name, severity)`` for the shared class, or None.
        """
        shared = med_classes & allergy_classes
        if not shared:
            return None
        candidates = [
            (class_name, severity)
            for class_name, severity, _members in _CROSS_REACTIVITY_CLASSES
            if class_name in shared
        ]
        return max(candidates, key=lambda item: _SEVERITY_RANK[item[1]])
