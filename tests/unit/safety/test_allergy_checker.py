"""Tests for the drug-allergy conflict checker."""

from __future__ import annotations

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
