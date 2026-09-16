"""Tests for clozapine + serial ANC declining/low trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import ClozapineAncTrendBridge as ExportedBridge
from medagent.safety.clozapine_anc_checker import ClozapineAncChecker
from medagent.safety.clozapine_anc_trend_bridge import ClozapineAncTrendBridge
from medagent.safety.clozapine_cyp1a2_checker import ClozapineCyp1a2Checker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_declining_anc_on_clozapine() -> None:
    labs = [
        {"name": "ANC", "value": 2800.0, "drawn_at": "2026-01-01"},
        {"name": "ANC", "value": 1400.0, "drawn_at": "2026-01-15"},
    ]
    findings = ClozapineAncTrendBridge().check(
        medications=_meds("Clozapine 300 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "declining_anc_on_clozapine")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.anc_values == [2800.0, 1400.0]


def test_critical_low_anc_on_clozapine() -> None:
    labs = [
        {"name": "absolute neutrophil count", "value": 1600.0, "drawn_at": "a"},
        {"name": "absolute neutrophil count", "value": 800.0, "drawn_at": "b"},
    ]
    findings = ClozapineAncTrendBridge().check(
        medications=_meds("Clozaril"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "critical_low_anc_on_clozapine")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_anc == 800.0


def test_rems_advisory() -> None:
    labs = [
        {"name": "neutrophil count", "value": 2200.0, "drawn_at": "1"},
        {"name": "neutrophil count", "value": 1300.0, "drawn_at": "2"},
    ]
    findings = ClozapineAncTrendBridge().check(
        medications=_meds("FazaClo"),
        labs=labs,
    )
    assert any(f.finding_kind == "clozapine_anc_rems_advisory" for f in findings)
    assert any(f.finding_kind == "declining_anc_on_clozapine" for f in findings)


def test_no_clozapine_no_findings() -> None:
    labs = [
        {"name": "ANC", "value": 2500.0, "drawn_at": "1"},
        {"name": "ANC", "value": 900.0, "drawn_at": "2"},
    ]
    assert ClozapineAncTrendBridge().check(medications=_meds("Olanzapine"), labs=labs) == []


def test_clozapine_stable_anc_no_findings() -> None:
    labs = [
        {"name": "ANC", "value": 3200.0, "drawn_at": "1"},
        {"name": "ANC", "value": 3100.0, "drawn_at": "2"},
    ]
    findings = ClozapineAncTrendBridge().check(
        medications=_meds("Clozapine"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = ClozapineAncTrendBridge().check(
        medications=_meds("Clozapine"),
        labs=[
            {"name": "ANC", "value": 1200.0, "drawn_at": "2026-01-05"},
            {"name": "ANC", "value": 2500.0, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "declining_anc_on_clozapine")
    assert hit.anc_values == [2500.0, 1200.0]


def test_distinct_from_anc_checker_and_cyp1a2() -> None:
    assert ClozapineAncTrendBridge is not ClozapineAncChecker
    assert ClozapineAncTrendBridge is not ClozapineCyp1a2Checker
    meds = _meds("Clozapine")
    labs = [
        {"name": "ANC", "value": 2600.0, "drawn_at": "a"},
        {"name": "ANC", "value": 1100.0, "drawn_at": "b"},
    ]
    assert ClozapineAncTrendBridge().check(medications=meds, labs=labs)
    assert ClozapineAncChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = ClozapineAncTrendBridge().check(
        medications=_meds("Pseudoclozapine"),
        labs=[
            {"name": "ANC", "value": 2500.0, "drawn_at": "1"},
            {"name": "ANC", "value": 900.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Clozapine", "Versacloz")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "ANC", "value": 2400.0, "drawn_at": "d1"},
        {"name": "ANC", "value": 1350.0, "drawn_at": "d2"},
    ]
    findings = ClozapineAncTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Clozaril"),
        labs=[
            {"name": "ANC", "value": 2000.0, "drawn_at": "d1"},
            {"name": "ANC", "value": 950.0, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
