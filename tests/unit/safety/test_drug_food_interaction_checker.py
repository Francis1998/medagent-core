"""Tests for the drug–food interaction safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety.drug_food_interaction_checker import DrugFoodInteractionChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names.

    Args:
        names: Medication name strings.

    Returns:
        Medication objects for each name.
    """
    return [Medication(name=name) for name in names]


def test_grapefruit_with_simvastatin_is_flagged() -> None:
    """Grapefruit with simvastatin is a HIGH CYP3A4 interaction."""
    findings = DrugFoodInteractionChecker().check(_meds("Simvastatin 20 mg"), ["grapefruit"])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "simvastatin"
    assert finding.food_category == "grapefruit"
    assert finding.severity is Severity.HIGH


def test_grapefruit_with_atorvastatin_is_flagged() -> None:
    """Grapefruit with atorvastatin is also flagged."""
    findings = DrugFoodInteractionChecker().check(_meds("Atorvastatin"), ["grapefruit juice"])

    assert len(findings) == 1
    assert findings[0].agent == "atorvastatin"
    assert findings[0].food_category == "grapefruit"


def test_dairy_with_tetracycline_is_flagged() -> None:
    """Dairy with tetracycline is a MODERATE absorption interaction."""
    findings = DrugFoodInteractionChecker().check(_meds("Tetracycline"), ["dairy"])

    assert len(findings) == 1
    assert findings[0].agent == "tetracycline"
    assert findings[0].food_category == "dairy"
    assert findings[0].severity is Severity.MODERATE


def test_dairy_with_ciprofloxacin_is_flagged() -> None:
    """Dairy/milk with ciprofloxacin is flagged as reduced absorption."""
    findings = DrugFoodInteractionChecker().check(_meds("Ciprofloxacin"), ["milk"])

    assert len(findings) == 1
    assert findings[0].agent == "ciprofloxacin"
    assert findings[0].food_category == "dairy"


def test_tyramine_with_maoi_is_critical() -> None:
    """Tyramine with an MAOI is CRITICAL (hypertensive-crisis risk)."""
    findings = DrugFoodInteractionChecker().check(_meds("Phenelzine"), ["tyramine"])

    assert len(findings) == 1
    assert findings[0].agent == "phenelzine"
    assert findings[0].food_category == "tyramine"
    assert findings[0].severity is Severity.CRITICAL


def test_tyramine_with_tranylcypromine_is_flagged() -> None:
    """Tyramine with tranylcypromine is also flagged."""
    findings = DrugFoodInteractionChecker().check(_meds("Tranylcypromine"), ["tyramine-rich foods"])

    assert len(findings) == 1
    assert findings[0].agent == "tranylcypromine"


def test_alcohol_with_metronidazole_is_flagged() -> None:
    """Alcohol with metronidazole is a HIGH disulfiram-like interaction."""
    findings = DrugFoodInteractionChecker().check(_meds("Metronidazole"), ["alcohol"])

    assert len(findings) == 1
    assert findings[0].agent == "metronidazole"
    assert findings[0].food_category == "alcohol"
    assert findings[0].severity is Severity.HIGH


def test_alcohol_with_disulfiram_is_flagged() -> None:
    """Alcohol with disulfiram is flagged."""
    findings = DrugFoodInteractionChecker().check(_meds("Disulfiram"), ["ethanol"])

    assert len(findings) == 1
    assert findings[0].agent == "disulfiram"
    assert findings[0].food_category == "alcohol"


def test_unrelated_medication_or_flag_yields_no_finding() -> None:
    """An unrelated drug/flag pair produces no finding."""
    checker = DrugFoodInteractionChecker()

    assert checker.check(_meds("Metformin"), ["grapefruit"]) == []
    assert checker.check(_meds("Simvastatin"), ["dairy"]) == []
    assert checker.check(_meds("Simvastatin"), []) == []
    assert checker.check([], ["grapefruit"]) == []


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Food and drug aliases match whole tokens, not loose substrings.

    ``milkweed`` must not match the dairy alias ``milk``, and a medication
    whose name merely contains ``statin`` as a substring of another word must
    not match ``simvastatin`` / ``atorvastatin``.
    """
    findings = DrugFoodInteractionChecker().check(_meds("Metformin"), ["milkweed tea"])

    assert findings == []


def test_findings_ordered_by_descending_severity() -> None:
    """Findings are ordered by descending severity then medication name."""
    findings = DrugFoodInteractionChecker().check(
        _meds("Tetracycline", "Phenelzine", "Simvastatin"),
        ["dairy", "tyramine", "grapefruit"],
    )

    assert [finding.agent for finding in findings] == [
        "phenelzine",
        "simvastatin",
        "tetracycline",
    ]
    assert [finding.severity for finding in findings] == [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MODERATE,
    ]
