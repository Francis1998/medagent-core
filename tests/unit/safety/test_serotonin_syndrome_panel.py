"""Tests for serotonin syndrome panel (aggregate multi-serotonergic load)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import SerotoninSyndromePanel as ExportedPanel
from medagent.safety.serotonin_syndrome_panel import SerotoninSyndromePanel


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_multi_serotonergic_stack() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Sertraline", "Tramadol"),
    )
    multi = next(f for f in findings if f.finding_kind == "multi_serotonergic_stack")
    assert multi.severity is Severity.HIGH
    assert set(multi.agents) == {"sertraline", "tramadol"}
    assert "RESEARCH USE ONLY" in multi.rationale


def test_maoi_serotonergic_stack() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Phenelzine", "Fluoxetine"),
    )
    maoi = next(f for f in findings if f.finding_kind == "maoi_serotonergic_stack")
    assert maoi.severity is Severity.CRITICAL
    assert "phenelzine" in maoi.maois


def test_methylene_blue_panel_aggregate() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Methylene Blue", "Escitalopram", "Sumatriptan"),
    )
    assert any(f.finding_kind == "maoi_serotonergic_stack" for f in findings)
    assert any(f.finding_kind == "multi_class_serotonergic_stack" for f in findings)
    maoi = next(f for f in findings if f.finding_kind == "maoi_serotonergic_stack")
    assert "methylene" in maoi.maois


def test_ssri_snri_triptan_stack() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Venlafaxine", "Sumatriptan"),
    )
    stack = next(f for f in findings if f.finding_kind == "ssri_snri_triptan_stack")
    assert stack.severity is Severity.HIGH
    assert stack.triptans == ["sumatriptan"]


def test_ssri_snri_serotonergic_opioid_stack() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Duloxetine", "Tramadol"),
    )
    stack = next(f for f in findings if f.finding_kind == "ssri_snri_serotonergic_opioid_stack")
    assert stack.serotonergic_opioids == ["tramadol"]


def test_multi_class_requires_three_classes() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Sertraline", "Sumatriptan", "Tramadol"),
    )
    multi_class = next(f for f in findings if f.finding_kind == "multi_class_serotonergic_stack")
    assert len(multi_class.pharmacologic_classes) >= 3


def test_no_findings_for_single_agent() -> None:
    findings = SerotoninSyndromePanel().check(medications=_meds("Sertraline"))
    assert findings == []


def test_no_findings_for_benign_meds() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Metformin", "Lisinopril"),
    )
    assert findings == []


def test_deduplicates_same_agent() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Sertraline 50mg", "Sertraline tablet", "Tramadol"),
    )
    multi = next(f for f in findings if f.finding_kind == "multi_serotonergic_stack")
    assert multi.agents.count("sertraline") == 1
    assert multi.stack_size == 2


def test_whole_token_matching() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Pseudosertraline", "Ultramoid"),
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = SerotoninSyndromePanel().check(
        medications=_meds("Linezolid", "Sertraline", "Sumatriptan"),
    )
    assert findings
    assert findings[0].severity is Severity.CRITICAL


def test_exported_from_safety_package() -> None:
    findings = ExportedPanel().check(
        medications=_meds("Paroxetine", "Tramadol"),
    )
    assert any(f.finding_kind == "multi_serotonergic_stack" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
