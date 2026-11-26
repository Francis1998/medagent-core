"""Tests for the drug-allergy conflict checker."""

from __future__ import annotations

import pytest

from medagent.models import Medication, Severity
from medagent.safety.allergy_checker import AllergyChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_direct_conflict_exact_name() -> None:
    """A medication equal to a documented allergen is a direct conflict."""
    conflicts = AllergyChecker().check(_meds("Amoxicillin"), ["amoxicillin"])

    assert len(conflicts) == 1
    assert conflicts[0].match_type == "direct"
    assert conflicts[0].severity is Severity.HIGH


def test_direct_conflict_component_token() -> None:
    """An allergen appearing as a component of a compound med name matches."""
    conflicts = AllergyChecker().check(_meds("Penicillin V Potassium"), ["penicillin"])

    assert len(conflicts) == 1
    assert conflicts[0].match_type == "direct"


def test_cross_reactivity_within_class() -> None:
    """A same-class medication conflicts with an allergen via cross-reactivity."""
    conflicts = AllergyChecker().check(_meds("Amoxicillin"), ["penicillin"])

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.match_type == "cross_reactivity"
    assert conflict.drug_class == "penicillins"
    assert conflict.severity is Severity.HIGH


def test_no_conflict_for_unrelated_drug() -> None:
    """An unrelated medication produces no conflict."""
    conflicts = AllergyChecker().check(_meds("Metformin"), ["penicillin"])

    assert conflicts == []


def test_direct_takes_precedence_over_cross_reactivity() -> None:
    """A direct match is not also reported as a cross-reactivity match."""
    conflicts = AllergyChecker().check(_meds("Amoxicillin"), ["amoxicillin"])

    assert len(conflicts) == 1
    assert conflicts[0].match_type == "direct"


def test_multiple_medications_and_allergies() -> None:
    """Each conflicting medication/allergy pair is reported independently."""
    conflicts = AllergyChecker().check(
        _meds("Ibuprofen", "Metformin", "Cephalexin"),
        ["aspirin", "cefazolin"],
    )

    pairs = {(c.medication, c.drug_class) for c in conflicts}
    assert ("Ibuprofen", "nsaids") in pairs
    assert ("Cephalexin", "cephalosporins") in pairs
    # Metformin is unrelated to any documented allergen.
    assert all(c.medication != "Metformin" for c in conflicts)


def test_empty_inputs_return_no_conflicts() -> None:
    """Empty medications or allergies yield no conflicts."""
    checker = AllergyChecker()

    assert checker.check([], ["penicillin"]) == []
    assert checker.check(_meds("Amoxicillin"), []) == []
    assert checker.check(_meds("Amoxicillin"), ["   "]) == []


@pytest.mark.parametrize(
    ("allergy", "medication", "drug_class", "severity"),
    [
        ("Penicillins", "Amoxicillin 500 mg capsule", "penicillins", Severity.HIGH),
        ("Allergy to penicillins", "Piperacillin-tazobactam 4.5 g", "penicillins", Severity.HIGH),
        ("Cephalosporin", "Cefazolin 1 g injection", "cephalosporins", Severity.MODERATE),
        ("Cephalosporins", "Ceftriaxone 1 g injection", "cephalosporins", Severity.MODERATE),
        ("Sulfa", "Sulfamethoxazole-trimethoprim 800-160 mg", "sulfonamides", Severity.HIGH),
        ("Sulfa (Sulfonamide Antibiotics)", "Bactrim DS", "sulfonamides", Severity.HIGH),
        ("Sulfonamides", "Sulfadiazine 500 mg tablet", "sulfonamides", Severity.HIGH),
        ("NSAIDs", "Ibuprofen 400 mg tablet", "nsaids", Severity.MODERATE),
        ("Non-steroidal anti-inflammatory agent", "Naproxen 500 mg", "nsaids", Severity.MODERATE),
        ("Nonsteroidal anti-inflammatory drugs", "Ketorolac 30 mg", "nsaids", Severity.MODERATE),
    ],
)
def test_an_allergy_recorded_as_a_drug_class_flags_the_class_members(
    allergy: str, medication: str, drug_class: str, severity: Severity
) -> None:
    """An allergy named by its class ("Penicillins", "Sulfa", "NSAIDs") covers every member."""
    conflicts = AllergyChecker().check(_meds(medication), [allergy])

    assert [(c.match_type, c.drug_class, c.severity) for c in conflicts] == [
        ("cross_reactivity", drug_class, severity)
    ]


@pytest.mark.parametrize(
    ("allergy", "medication"),
    [
        ("Sulfa", "Morphine sulfate 15 mg tablet"),
        ("Steroidal anti-inflammatory agent", "Ibuprofen 400 mg tablet"),
        ("Penicillins", "Cefazolin 1 g injection"),
    ],
)
def test_class_names_match_whole_tokens_and_their_own_class_only(
    allergy: str, medication: str
) -> None:
    """``sulfate`` is not ``sulfa``, a steroid is not an NSAID, and classes stay separate."""
    assert AllergyChecker().check(_meds(medication), [allergy]) == []
