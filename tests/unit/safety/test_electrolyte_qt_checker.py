"""Tests for the electrolyte panel (K/Mg) with QT drug safety checker."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import ElectrolyteQtChecker as ExportedChecker
from medagent.safety.electrolyte_qt_checker import ElectrolyteQtChecker


def _meds(*names: str) -> list[Medication]:
    """Build a medication list from names."""
    return [Medication(name=name) for name in names]


def test_no_findings_without_qt_drug() -> None:
    """Non-QT medications yield no findings even when electrolytes are low."""
    findings = ElectrolyteQtChecker().check(
        _meds("Metformin 500 mg BID"),
        potassium_mmol_l=3.0,
        magnesium_mg_dl=1.2,
    )

    assert findings == []


def test_no_findings_when_electrolytes_adequate() -> None:
    """QT drug with normal electrolytes yields no findings."""
    findings = ElectrolyteQtChecker().check(
        _meds("Amiodarone 200 mg daily"),
        potassium_mmol_l=4.0,
        magnesium_mg_dl=2.0,
    )

    assert findings == []


def test_flags_missing_electrolytes() -> None:
    """QT drug without documented electrolytes yields missing_electrolytes."""
    findings = ElectrolyteQtChecker().check(
        _meds("Sotalol 80 mg BID"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "sotalol"
    assert finding.finding_kind == "missing_electrolytes"
    assert finding.severity is Severity.MODERATE
    assert "RESEARCH USE ONLY" in finding.rationale


def test_flags_low_potassium() -> None:
    """QT drug with low potassium yields low_potassium finding."""
    findings = ElectrolyteQtChecker().check(
        _meds("Citalopram 20 mg daily"),
        potassium_mmol_l=3.2,
        magnesium_mg_dl=2.0,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "low_potassium"
    assert findings[0].severity is Severity.HIGH
    assert findings[0].potassium_mmol_l == 3.2


def test_flags_low_magnesium() -> None:
    """QT drug with low magnesium yields low_magnesium finding."""
    findings = ElectrolyteQtChecker().check(
        _meds("Haloperidol 5 mg BID"),
        potassium_mmol_l=4.1,
        magnesium_mg_dl=1.5,
    )

    assert len(findings) == 1
    assert findings[0].finding_kind == "low_magnesium"
    assert findings[0].severity is Severity.HIGH


def test_missing_and_low_electrolytes_emit_multiple_kinds() -> None:
    """Missing magnesium plus low potassium yields both applicable finding kinds."""
    findings = ElectrolyteQtChecker().check(
        _meds("Methadone 10 mg daily"),
        potassium_mmol_l=3.1,
    )

    kinds = {finding.finding_kind for finding in findings}
    assert kinds == {"missing_electrolytes", "low_potassium"}


def test_multiple_qt_drugs_each_receive_findings() -> None:
    """Each distinct QT drug receives its own finding for the same electrolyte gap."""
    findings = ElectrolyteQtChecker().check(
        _meds("Amiodarone 200 mg daily", "Azithromycin 250 mg daily"),
        potassium_mmol_l=3.0,
        magnesium_mg_dl=2.0,
    )

    assert len(findings) == 2
    agents = {finding.agent for finding in findings}
    assert agents == {"amiodarone", "azithromycin"}


def test_whole_token_matching_avoids_substring_false_positives() -> None:
    """Substring look-alikes must not match panel agents."""
    findings = ElectrolyteQtChecker().check(
        _meds("Pseudoamiodarone compound"),
        potassium_mmol_l=3.0,
    )

    assert findings == []
    real = ElectrolyteQtChecker().check(
        _meds("Amiodarone 200 mg"),
        potassium_mmol_l=3.0,
        magnesium_mg_dl=2.0,
    )
    assert len(real) == 1


def test_checker_is_exported_from_safety_package() -> None:
    """The checker is available through the public safety package export."""
    findings = ExportedChecker().check(
        _meds("Dofetilide 500 mcg BID"),
        magnesium_mg_dl=1.4,
        potassium_mmol_l=4.0,
    )

    assert len(findings) == 1
    assert findings[0].agent == "dofetilide"
