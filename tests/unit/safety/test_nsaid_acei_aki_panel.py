"""Tests for NSAID + ACEI/ARB AKI/bleeding panel."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import NsaidAceiAkiPanel as ExportedPanel
from medagent.safety.nsaid_acei_aki_panel import NsaidAceiAkiPanel
from medagent.safety.triple_whammy_checker import TripleWhammyChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_dual_nsaid_acei_without_diuretic() -> None:
    findings = NsaidAceiAkiPanel().check(medications=_meds("Ibuprofen", "Lisinopril"))
    kinds = {f.finding_kind for f in findings}
    assert "nsaid_acei_dual_aki_panel" in kinds
    assert "nsaid_acei_diuretic_escalation" not in kinds
    hit = next(f for f in findings if f.finding_kind == "nsaid_acei_dual_aki_panel")
    assert hit.severity is Severity.HIGH
    assert hit.nsaids == ["ibuprofen"]
    assert hit.acei_arb_agents == ["lisinopril"]
    assert hit.diuretics == []
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    # Dual alone must NOT trip TripleWhammyChecker
    assert TripleWhammyChecker().check(medications=_meds("Ibuprofen", "Lisinopril")) == []


def test_escalates_when_diuretic_present() -> None:
    findings = NsaidAceiAkiPanel().check(
        medications=_meds("Naproxen", "Losartan", "Furosemide"),
    )
    dual = next(f for f in findings if f.finding_kind == "nsaid_acei_dual_aki_panel")
    esc = next(f for f in findings if f.finding_kind == "nsaid_acei_diuretic_escalation")
    assert dual.severity is Severity.CRITICAL
    assert esc.severity is Severity.CRITICAL
    assert "furosemide" in esc.diuretics
    assert "RESEARCH USE ONLY" in esc.rationale


def test_multi_nsaid_on_acei() -> None:
    findings = NsaidAceiAkiPanel().check(
        medications=_meds("Ibuprofen", "Meloxicam", "Valsartan"),
    )
    multi = next(f for f in findings if f.finding_kind == "multi_nsaid_on_acei_arb")
    assert set(multi.nsaids) == {"ibuprofen", "meloxicam"}
    assert multi.severity is Severity.HIGH


def test_no_findings_nsaid_only() -> None:
    assert NsaidAceiAkiPanel().check(medications=_meds("Ibuprofen", "Metformin")) == []


def test_no_findings_acei_only() -> None:
    assert NsaidAceiAkiPanel().check(medications=_meds("Lisinopril", "Metformin")) == []


def test_whole_token_matching() -> None:
    findings = NsaidAceiAkiPanel().check(
        medications=_meds("Pseudoibuprofen", "Lisinoprilx"),
    )
    assert findings == []


def test_deduplicates_same_agent() -> None:
    findings = NsaidAceiAkiPanel().check(
        medications=_meds("Ibuprofen 200mg", "Ibuprofen tablet", "Enalapril"),
    )
    hit = next(f for f in findings if f.finding_kind == "nsaid_acei_dual_aki_panel")
    assert hit.nsaids.count("ibuprofen") == 1


def test_findings_sorted_by_severity() -> None:
    findings = NsaidAceiAkiPanel().check(
        medications=_meds("Ibuprofen", "Lisinopril", "HCTZ"),
    )
    assert findings
    rank = {
        Severity.UNKNOWN: 0,
        Severity.LOW: 1,
        Severity.MODERATE: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }
    scores = [rank[f.severity] for f in findings]
    assert scores == sorted(scores, reverse=True)


def test_never_modifies_medications() -> None:
    meds = _meds("Ketorolac", "Ramipril", "Chlorthalidone")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    findings = NsaidAceiAkiPanel().check(medications=meds)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)


def test_exported_from_safety_package() -> None:
    findings = ExportedPanel().check(medications=_meds("Diclofenac", "Candesartan"))
    assert any(f.finding_kind == "nsaid_acei_dual_aki_panel" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
