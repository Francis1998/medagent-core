"""Tests for anticholinergic burden panel (aggregate ACB stack findings)."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import AnticholinergicBurdenPanel as ExportedPanel
from medagent.safety.anticholinergic_burden_panel import AnticholinergicBurdenPanel


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_acb_threshold_exceeded_single_strong() -> None:
    findings = AnticholinergicBurdenPanel().check(medications=_meds("Amitriptyline"))
    kinds = {f.finding_kind for f in findings}
    assert "acb_threshold_exceeded" in kinds
    assert "multi_strong_anticholinergic_stack" not in kinds
    hit = next(f for f in findings if f.finding_kind == "acb_threshold_exceeded")
    assert hit.total_acb_score == 3
    assert hit.agents == ["amitriptyline"]
    assert hit.severity is Severity.HIGH
    assert "RESEARCH USE ONLY" in hit.rationale


def test_high_acb_burden_multi_agent() -> None:
    findings = AnticholinergicBurdenPanel().check(
        medications=_meds("Ranitidine", "Trazodone", "Alprazolam"),
    )
    high = next(f for f in findings if f.finding_kind == "high_acb_burden")
    assert high.total_acb_score == 3
    assert set(high.agents) == {"ranitidine", "trazodone", "alprazolam"}
    assert "RESEARCH USE ONLY" in high.rationale


def test_multi_strong_anticholinergic_stack() -> None:
    findings = AnticholinergicBurdenPanel().check(
        medications=_meds("Amitriptyline", "Oxybutynin"),
    )
    stack = next(f for f in findings if f.finding_kind == "multi_strong_anticholinergic_stack")
    assert stack.severity is Severity.CRITICAL
    assert set(stack.agents) == {"amitriptyline", "oxybutynin"}
    assert stack.total_acb_score == 6
    assert any(f.finding_kind == "acb_threshold_exceeded" for f in findings)
    assert any(f.finding_kind == "high_acb_burden" for f in findings)


def test_no_findings_below_threshold() -> None:
    findings = AnticholinergicBurdenPanel().check(
        medications=_meds("Ranitidine", "Trazodone"),
    )
    assert findings == []


def test_no_findings_for_benign_meds() -> None:
    findings = AnticholinergicBurdenPanel().check(
        medications=_meds("Metformin", "Lisinopril"),
    )
    assert findings == []


def test_deduplicates_same_agent() -> None:
    findings = AnticholinergicBurdenPanel().check(
        medications=_meds("Amitriptyline 25mg", "Amitriptyline tablet", "Oxybutynin"),
    )
    stack = next(f for f in findings if f.finding_kind == "multi_strong_anticholinergic_stack")
    assert stack.agents.count("amitriptyline") == 1
    assert stack.total_acb_score == 6


def test_whole_token_matching() -> None:
    findings = AnticholinergicBurdenPanel().check(
        medications=_meds("Pseudoamitriptyline", "Oxybutyninex"),
    )
    assert findings == []


def test_findings_sorted_by_severity() -> None:
    findings = AnticholinergicBurdenPanel().check(
        medications=_meds("Diphenhydramine", "Oxybutynin", "Quetiapine"),
    )
    assert findings
    assert findings[0].severity is Severity.CRITICAL
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
    meds = _meds("Amitriptyline", "Oxybutynin")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    findings = AnticholinergicBurdenPanel().check(medications=meds)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
    assert all("Never modifies medications" in f.rationale for f in findings)


def test_exported_from_safety_package() -> None:
    findings = ExportedPanel().check(
        medications=_meds("Paroxetine", "Diphenhydramine"),
    )
    assert any(f.finding_kind == "multi_strong_anticholinergic_stack" for f in findings)
    assert any(f.finding_kind == "acb_threshold_exceeded" for f in findings)
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
