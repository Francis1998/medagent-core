"""Tests for isotretinoin absolute pregnancy contraindication gate."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import IsotretinoinPregnancyGate as ExportedGate
from medagent.safety.isotretinoin_pregnancy_gate import IsotretinoinPregnancyGate
from medagent.safety.isotretinoin_tetracycline_checker import IsotretinoinTetracyclineChecker
from medagent.safety.pregnancy_checker import PregnancySafetyChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_absolute_pregnancy_contraindication() -> None:
    findings = IsotretinoinPregnancyGate().check(
        medications=_meds("Isotretinoin 40 mg"),
        pregnant=True,
    )
    hit = next(
        f for f in findings if f.finding_kind == "isotretinoin_absolute_pregnancy_contraindication"
    )
    assert hit.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.pregnant is True


def test_pregnancy_prevention_required() -> None:
    findings = IsotretinoinPregnancyGate().check(
        medications=_meds("Accutane"),
        pregnancy_capable=True,
    )
    hit = next(
        f for f in findings if f.finding_kind == "isotretinoin_pregnancy_prevention_required"
    )
    assert hit.severity is Severity.HIGH
    assert hit.pregnancy_capable is True


def test_teratogen_gate_aggregate() -> None:
    findings = IsotretinoinPregnancyGate().check(
        medications=_meds("Claravis"),
        pregnant=True,
    )
    assert any(f.finding_kind == "isotretinoin_teratogen_gate" for f in findings)


def test_no_context_no_findings() -> None:
    assert (
        IsotretinoinPregnancyGate().check(
            medications=_meds("Isotretinoin"),
            pregnant=False,
            pregnancy_capable=False,
        )
        == []
    )


def test_no_isotretinoin_no_findings() -> None:
    assert (
        IsotretinoinPregnancyGate().check(
            medications=_meds("Doxycycline"),
            pregnant=True,
        )
        == []
    )


def test_brand_agents() -> None:
    for brand in ("Absorica", "Myorisan", "Zenatane"):
        findings = IsotretinoinPregnancyGate().check(
            medications=_meds(brand),
            pregnant=True,
        )
        assert findings


def test_distinct_from_pregnancy_and_tetracycline() -> None:
    assert IsotretinoinPregnancyGate is not PregnancySafetyChecker
    assert IsotretinoinPregnancyGate is not IsotretinoinTetracyclineChecker
    meds = _meds("Isotretinoin", "Doxycycline")
    gate = IsotretinoinPregnancyGate().check(medications=meds, pregnant=True)
    preg = PregnancySafetyChecker().check(meds, pregnant=True)
    tetra = IsotretinoinTetracyclineChecker().check(meds)
    assert gate
    assert preg
    assert tetra


def test_whole_token_matching() -> None:
    findings = IsotretinoinPregnancyGate().check(
        medications=_meds("Pseudoisotretinoin"),
        pregnant=True,
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Isotretinoin", "Accutane")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    findings = IsotretinoinPregnancyGate().check(medications=meds, pregnant=True)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedGate().check(medications=_meds("Isotretinoin"), pregnant=True)
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
