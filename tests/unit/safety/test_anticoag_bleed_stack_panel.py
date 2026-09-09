"""Tests for anticoag bleed stack panel (aggregate multi-agent hemorrhage)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AnticoagBleedStackPanel as ExportedPanel
from medagent.safety.anticoag_bleed_stack_panel import AnticoagBleedStackPanel


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_triple_stack() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Warfarin", "Aspirin", "Ibuprofen"),
    )
    triple = next(f for f in findings if f.finding_kind == "triple_stack")
    assert triple.severity is Severity.CRITICAL
    assert set(triple.anticoagulants) == {"warfarin"}
    assert set(triple.antiplatelets) == {"aspirin"}
    assert set(triple.nsaids) == {"ibuprofen"}
    assert "RESEARCH USE ONLY" in triple.rationale


def test_anticoag_antiplatelet_stack() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Apixaban", "Clopidogrel"),
    )
    stack = next(f for f in findings if f.finding_kind == "anticoag_antiplatelet_stack")
    assert stack.severity is Severity.CRITICAL
    assert stack.antiplatelets == ["clopidogrel"]


def test_anticoag_nsaid_stack() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Rivaroxaban", "Naproxen"),
    )
    stack = next(f for f in findings if f.finding_kind == "anticoag_nsaid_stack")
    assert stack.severity is Severity.HIGH
    assert stack.nsaids == ["naproxen"]


def test_dual_antiplatelet_on_anticoag() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Warfarin", "Aspirin", "Clopidogrel"),
    )
    dual = next(f for f in findings if f.finding_kind == "dual_antiplatelet_on_anticoag")
    assert dual.severity is Severity.CRITICAL
    assert set(dual.antiplatelets) == {"aspirin", "clopidogrel"}


def test_multi_anticoag_stack() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Warfarin", "Enoxaparin"),
    )
    multi = next(f for f in findings if f.finding_kind == "multi_anticoag_stack")
    assert multi.severity is Severity.HIGH
    assert set(multi.anticoagulants) == {"warfarin", "enoxaparin"}


def test_no_findings_without_anticoagulant() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Aspirin", "Ibuprofen"),
    )
    assert findings == []


def test_no_findings_for_benign_meds() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Metformin", "Lisinopril"),
    )
    assert findings == []


def test_deduplicates_same_agent() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Warfarin 5mg", "Warfarin tablet", "Ibuprofen"),
    )
    stack = next(f for f in findings if f.finding_kind == "anticoag_nsaid_stack")
    assert stack.anticoagulants == ["warfarin"]
    assert stack.stack_size == 2


def test_whole_token_matching() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Pseudowarfarin", "Aspirinoid"),
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = AnticoagBleedStackPanel().check(
        medications=_meds("Apixaban", "Aspirin", "Ibuprofen"),
    )
    assert findings
    assert findings[0].severity is Severity.CRITICAL


def test_exported_from_safety_package() -> None:
    findings = ExportedPanel().check(
        medications=_meds("Dabigatran", "Ketorolac"),
    )
    assert any(f.finding_kind == "anticoag_nsaid_stack" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
