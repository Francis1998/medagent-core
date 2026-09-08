"""Tests for QT prolongation panel (aggregate multi-drug risk)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import QtProlongationPanel as ExportedPanel
from medagent.safety.qt_prolongation_panel import QtProlongationPanel


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_multi_agent_aggregate() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Azithromycin", "Ondansetron"),
    )
    kinds = {f.finding_kind for f in findings}
    assert "multi_agent_aggregate" in kinds
    aggregate = next(f for f in findings if f.finding_kind == "multi_agent_aggregate")
    assert aggregate.agent_count == 2
    assert set(aggregate.agents) == {"azithromycin", "ondansetron"}
    assert "RESEARCH USE ONLY" in aggregate.rationale
    assert aggregate.severity in {Severity.MODERATE, Severity.HIGH}


def test_three_agents_elevates_severity() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Amiodarone", "Haloperidol", "Ondansetron"),
    )
    aggregate = next(f for f in findings if f.finding_kind == "multi_agent_aggregate")
    assert aggregate.agent_count == 3
    assert aggregate.severity is Severity.CRITICAL


def test_same_class_cluster_macrolides() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Azithromycin", "Clarithromycin"),
    )
    cluster = next(f for f in findings if f.finding_kind == "same_class_cluster")
    assert cluster.pharmacologic_classes == ["macrolide"]
    assert set(cluster.agents) == {"azithromycin", "clarithromycin"}
    assert cluster.severity is Severity.HIGH


def test_context_amplified_high_qtc() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Methadone"),
        qtc_ms=520.0,
    )
    context = next(f for f in findings if f.finding_kind == "context_amplified")
    assert context.qtc_ms == 520.0
    assert context.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in context.rationale


def test_context_low_potassium() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Sotalol"),
        potassium_mmol_l=3.1,
    )
    context = next(f for f in findings if f.finding_kind == "context_amplified")
    assert context.potassium_mmol_l == 3.1
    assert context.severity is Severity.HIGH


def test_single_agent_panel() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Citalopram 20mg"),
    )
    assert len(findings) == 1
    assert findings[0].finding_kind == "single_agent_panel"
    assert findings[0].agents == ["citalopram"]


def test_no_findings_for_non_qt_meds() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Metformin", "Lisinopril"),
    )
    assert findings == []


def test_deduplicates_same_agent_listed_twice() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Amiodarone 200mg", "Amiodarone tablet"),
    )
    assert len(findings) == 1
    assert findings[0].finding_kind == "single_agent_panel"
    assert findings[0].agent_count == 1


def test_whole_token_matching() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Haloperidoloid compound"),
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = QtProlongationPanel().check(
        medications=_meds("Azithromycin", "Erythromycin"),
        qtc_ms=505.0,
    )
    assert findings
    assert findings[0].severity is Severity.CRITICAL


def test_exported_from_safety_package() -> None:
    findings = ExportedPanel().check(
        medications=_meds("Levofloxacin", "Fluconazole"),
    )
    assert any(f.finding_kind == "multi_agent_aggregate" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
