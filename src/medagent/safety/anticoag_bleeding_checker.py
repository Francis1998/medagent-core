"""Anticoagulation bleeding-risk safety checker.

Co-prescribing an anticoagulant with an antiplatelet, NSAID, or SSRI increases
the risk of major hemorrhage through additive anticoagulation, platelet
dysfunction, and GI mucosal injury. These hazards are distinct from duplicate
anticoagulant therapy, generic drug-drug interaction screening, renal/hepatic
dose appropriateness, and boxed-warning single-agent flagging.

This checker focuses on a conservative panel of anticoagulant × augmenter
combinations. It emits one finding per unique canonical pair across distinct
medication entries, uses whole-token matching (never loose substrings), and is
deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AnticoagBleedingRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical anticoagulant token -> short mechanism descriptor.
_ANTICOAGULANTS: Final[dict[str, str]] = {
    "warfarin": "vitamin K antagonist anticoagulation",
    "apixaban": "direct factor Xa inhibition",
    "rivaroxaban": "direct factor Xa inhibition",
    "dabigatran": "direct thrombin inhibition",
    "enoxaparin": "low-molecular-weight heparin anticoagulation",
    "heparin": "unfractionated heparin anticoagulation",
}

# Canonical augmenter token -> (category, severity, mechanism, clinical consequence).
_BLEEDING_AUGMENTERS: Final[dict[str, tuple[str, Severity, str, str]]] = {
    # Antiplatelet agents — dual pathway blockade with anticoagulation.
    "aspirin": (
        "antiplatelet",
        Severity.CRITICAL,
        "additive anticoagulation plus irreversible platelet cyclooxygenase inhibition",
        "major GI bleeding, intracranial hemorrhage, or life-threatening hemorrhage",
    ),
    "clopidogrel": (
        "antiplatelet",
        Severity.CRITICAL,
        "additive anticoagulation plus P2Y12-mediated platelet inhibition",
        "major GI bleeding, intracranial hemorrhage, or life-threatening hemorrhage",
    ),
    "prasugrel": (
        "antiplatelet",
        Severity.CRITICAL,
        "additive anticoagulation plus potent P2Y12 platelet inhibition",
        "major GI bleeding, intracranial hemorrhage, or life-threatening hemorrhage",
    ),
    "ticagrelor": (
        "antiplatelet",
        Severity.CRITICAL,
        "additive anticoagulation plus reversible P2Y12 platelet inhibition",
        "major GI bleeding, intracranial hemorrhage, or life-threatening hemorrhage",
    ),
    # NSAIDs — GI mucosal injury layered on anticoagulation.
    "ibuprofen": (
        "NSAID",
        Severity.HIGH,
        "anticoagulation plus NSAID-associated GI mucosal injury and platelet dysfunction",
        "major GI bleeding or clinically significant hemorrhage",
    ),
    "naproxen": (
        "NSAID",
        Severity.HIGH,
        "anticoagulation plus NSAID-associated GI mucosal injury and platelet dysfunction",
        "major GI bleeding or clinically significant hemorrhage",
    ),
    "diclofenac": (
        "NSAID",
        Severity.HIGH,
        "anticoagulation plus NSAID-associated GI mucosal injury and platelet dysfunction",
        "major GI bleeding or clinically significant hemorrhage",
    ),
    "ketorolac": (
        "NSAID",
        Severity.HIGH,
        "anticoagulation plus potent NSAID GI mucosal injury",
        "major GI bleeding or clinically significant hemorrhage",
    ),
    "meloxicam": (
        "NSAID",
        Severity.HIGH,
        "anticoagulation plus NSAID-associated GI mucosal injury and platelet dysfunction",
        "major GI bleeding or clinically significant hemorrhage",
    ),
    "celecoxib": (
        "NSAID",
        Severity.HIGH,
        "anticoagulation plus COX-2 selective NSAID-associated bleeding risk",
        "major GI bleeding or clinically significant hemorrhage",
    ),
    "indomethacin": (
        "NSAID",
        Severity.HIGH,
        "anticoagulation plus NSAID-associated GI mucosal injury and platelet dysfunction",
        "major GI bleeding or clinically significant hemorrhage",
    ),
    # SSRIs — platelet serotonin uptake inhibition augments bleeding.
    "sertraline": (
        "SSRI",
        Severity.MODERATE,
        "anticoagulation plus SSRI-associated platelet dysfunction",
        "increased bruising, epistaxis, or major bleeding",
    ),
    "fluoxetine": (
        "SSRI",
        Severity.MODERATE,
        "anticoagulation plus SSRI-associated platelet dysfunction",
        "increased bruising, epistaxis, or major bleeding",
    ),
    "paroxetine": (
        "SSRI",
        Severity.MODERATE,
        "anticoagulation plus SSRI-associated platelet dysfunction",
        "increased bruising, epistaxis, or major bleeding",
    ),
    "citalopram": (
        "SSRI",
        Severity.MODERATE,
        "anticoagulation plus SSRI-associated platelet dysfunction",
        "increased bruising, epistaxis, or major bleeding",
    ),
    "escitalopram": (
        "SSRI",
        Severity.MODERATE,
        "anticoagulation plus SSRI-associated platelet dysfunction",
        "increased bruising, epistaxis, or major bleeding",
    ),
    "fluvoxamine": (
        "SSRI",
        Severity.MODERATE,
        "anticoagulation plus SSRI-associated platelet dysfunction",
        "increased bruising, epistaxis, or major bleeding",
    ),
}


class AnticoagBleedingChecker:
    """Flag anticoagulant combinations with antiplatelet, NSAID, or SSRI agents."""

    def check(self, medications: list[Medication]) -> list[AnticoagBleedingRisk]:
        """Return findings for anticoagulant × bleeding-risk augmenter pairs.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`AnticoagBleedingRisk` per unique canonical anticoagulant ×
            augmenter pair across distinct medication entries, ordered by
            descending severity then combination id. Duplicate entries for the
            same agent are de-duplicated, and a single medication entry naming
            both agents is not treated as a co-prescribed pair by itself.
        """
        anticoagulant_to_medications: dict[str, list[Medication]] = {}
        augmenter_to_medications: dict[str, list[Medication]] = {}
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            for agent in sorted(tokens & set(_ANTICOAGULANTS)):
                anticoagulant_to_medications.setdefault(agent, []).append(medication)
            for agent in sorted(tokens & set(_BLEEDING_AUGMENTERS)):
                augmenter_to_medications.setdefault(agent, []).append(medication)

        findings: list[AnticoagBleedingRisk] = []
        for anticoagulant_agent in sorted(_ANTICOAGULANTS):
            anticoagulant_medications = anticoagulant_to_medications.get(anticoagulant_agent, [])
            if not anticoagulant_medications:
                continue
            for augmenter_agent in sorted(_BLEEDING_AUGMENTERS):
                augmenter_medications = augmenter_to_medications.get(augmenter_agent, [])
                if not augmenter_medications:
                    continue
                matched_medications = self._select_distinct_medications(
                    anticoagulant_medications,
                    augmenter_medications,
                )
                if matched_medications is None:
                    continue
                med_a, med_b = matched_medications
                augmenter_rule = _BLEEDING_AUGMENTERS[augmenter_agent]
                augmenter_category, severity, mechanism, clinical_consequence = augmenter_rule
                anticoagulant_mechanism = _ANTICOAGULANTS[anticoagulant_agent]
                combination_id = f"ANTICOAG-BLEED-{anticoagulant_agent}-{augmenter_agent}"
                findings.append(
                    AnticoagBleedingRisk(
                        medication_a=med_a.name,
                        medication_b=med_b.name,
                        anticoagulant_agent=anticoagulant_agent,
                        augmenter_agent=augmenter_agent,
                        augmenter_category=augmenter_category,
                        combination_id=combination_id,
                        severity=severity,
                        mechanism=(f"{anticoagulant_mechanism} combined with {mechanism.lower()}"),
                        clinical_consequence=clinical_consequence,
                        rationale=(
                            "RESEARCH USE ONLY: "
                            f"Medications '{med_a.name}' ({anticoagulant_agent}) and "
                            f"'{med_b.name}' ({augmenter_agent}) match {combination_id}: "
                            f"{anticoagulant_mechanism} combined with {mechanism.lower()}. "
                            f"Clinical concern: {clinical_consequence}. Review indication, "
                            "dose, duration, and bleeding-risk mitigation with a qualified "
                            "clinician before any medication change."
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.combination_id,
            )
        )
        logger.info("anticoag_bleeding_checked", findings=len(findings))
        return findings

    @staticmethod
    def _select_distinct_medications(
        anticoagulant_medications: list[Medication],
        augmenter_medications: list[Medication],
    ) -> tuple[Medication, Medication] | None:
        """Choose the first two distinct medication entries for a candidate pair."""
        for medication_a in anticoagulant_medications:
            for medication_b in augmenter_medications:
                if medication_a is not medication_b:
                    return medication_a, medication_b
        return None

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
