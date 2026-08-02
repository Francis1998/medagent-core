"""Tests for the digoxin toxicity risk safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import DigoxinToxicityChecker as ExportedChecker
from medagent.safety.digoxin_toxicity_checker import DigoxinToxicityChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_digoxin() -> None:
    """Non-digoxin medications yield no findings."""
    findings = DigoxinToxicityChecker().check(
        _meds("Furosemide 40 mg daily"),
        potassium_mmol_l=3.0,
    )

    assert findings == []


def test_no_findings_when_electrolytes_adequate() -> None:
    """Digoxin with normal electrolytes and no loop diuretic yields no findings."""
    findings = DigoxinToxicityChecker().check(
        _meds("Digoxin 0.125 mg daily"),
        potassium_mmol_l=4.0,
        magnesium_mg_dl=2.0,
    )

    assert findings == []


def test_flags_low_potassium() -> None:
    """Digoxin with hypokalemia is flagged CRITICAL."""
    findings = DigoxinToxicityChecker().check(
        _meds("Digoxin 0.25 mg daily"),
        potassium_mmol_l=3.0,
        magnesium_mg_dl=2.0,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "digoxin"
    assert finding.finding_kind == "low_potassium"
    assert finding.severity is Severity.CRITICAL
    assert finding.potassium_mmol_l == 3.0
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_low_magnesium() -> None:
    """Digoxin with hypomagnesemia is flagged CRITICAL."""
    findings = DigoxinToxicityChecker().check(
        _meds("Digoxin 0.125 mg daily"),
        potassium_mmol_l=4.2,
        magnesium_mg_dl=1.5,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "low_magnesium"
    assert findings[0].severity is Severity.CRITICAL


def test_flags_loop_diuretic_without_repletion() -> None:
    """Loop diuretic without K/Mg repletion cues is flagged HIGH."""
    findings = DigoxinToxicityChecker().check(
        _meds("Digoxin 0.125 mg daily", "Furosemide 40 mg BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_kind == "loop_diuretic_without_repletion"
    assert finding.severity is Severity.HIGH
    assert finding.loop_diuretic_agents_found == ["furosemide"]
    assert finding.repletion_agents_found == []


def test_loop_diuretic_with_repletion_suppresses_finding() -> None:
    """Documented potassium repletion suppresses loop_diuretic_without_repletion."""
    findings = DigoxinToxicityChecker().check(
        _meds(
            "Digoxin 0.125 mg daily",
            "Torsemide 20 mg daily",
            "Potassium chloride 20 mEq daily",
        ),
    )

    assert findings == []


def test_multiple_finding_kinds_can_coexist() -> None:
    """Low K and loop diuretic without repletion can both be emitted."""
    findings = DigoxinToxicityChecker().check(
        _meds("Digoxin 0.25 mg daily", "Bumetanide 1 mg BID"),
        potassium_mmol_l=3.2,
    )

    kinds = {finding.finding_kind for finding in findings}
    assert kinds == {"low_potassium", "loop_diuretic_without_repletion"}


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = DigoxinToxicityChecker().check(
        _meds("Pseudodigoxin compound"),
        potassium_mmol_l=3.0,
    )

    assert findings == []
    real = DigoxinToxicityChecker().check(
        _meds("Digoxin 0.125 mg daily"),
        potassium_mmol_l=3.0,
    )
    assert len(real) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Digoxin 0.125 mg daily", "Furosemide 40 mg daily"),
    )

    assert len(findings) == 1
    assert findings[0].agent == "digoxin"
