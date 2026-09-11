"""Tests for QTc electrolyte bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import QTcElectrolyteBridge as ExportedBridge
from medagent.safety.qtc_electrolyte_bridge import QTcElectrolyteBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_falling_k_on_qt_agent() -> None:
    labs = [
        {"name": "potassium", "value": 4.2, "unit": "mmol/L", "drawn_at": "2026-01-01T08:00:00Z"},
        {"name": "potassium", "value": 3.1, "unit": "mmol/L", "drawn_at": "2026-01-01T16:00:00Z"},
    ]
    findings = QTcElectrolyteBridge().check(
        medications=_meds("Azithromycin 500 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "falling_k_on_qt_agent")
    assert hit.severity is Severity.CRITICAL
    assert hit.k_values == [4.2, 3.1]
    assert "azithromycin" in hit.agents
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale


def test_falling_mg_on_qt_agent() -> None:
    labs = [
        {"name": "magnesium", "value": 2.0, "drawn_at": "a"},
        {"name": "magnesium", "value": 1.8, "drawn_at": "b"},
    ]
    findings = QTcElectrolyteBridge().check(
        medications=_meds("Ondansetron"),
        labs=labs,
    )
    assert any(f.finding_kind == "falling_mg_on_qt_agent" for f in findings)


def test_low_k_on_qt_agent() -> None:
    labs = [{"name": "potassium", "value": 3.2, "drawn_at": "t1"}]
    findings = QTcElectrolyteBridge().check(medications=_meds("Haloperidol"), labs=labs)
    hit = next(f for f in findings if f.finding_kind == "low_k_on_qt_agent")
    assert hit.severity is Severity.CRITICAL
    assert "Never modifies medications" in hit.rationale


def test_low_mg_on_qt_agent() -> None:
    labs = [{"name": "serum magnesium", "value": 1.4, "drawn_at": "t1"}]
    findings = QTcElectrolyteBridge().check(medications=_meds("Methadone"), labs=labs)
    hit = next(f for f in findings if f.finding_kind == "low_mg_on_qt_agent")
    assert hit.severity is Severity.CRITICAL


def test_multi_qt_agent_electrolyte_risk() -> None:
    labs = [
        {"name": "potassium", "value": 4.0, "drawn_at": "1"},
        {"name": "potassium", "value": 3.2, "drawn_at": "2"},
    ]
    findings = QTcElectrolyteBridge().check(
        medications=_meds("Sotalol", "Ondansetron"),
        labs=labs,
    )
    stack = next(f for f in findings if f.finding_kind == "multi_qt_agent_electrolyte_risk")
    assert stack.severity is Severity.CRITICAL
    assert "Never modifies medications" in stack.rationale


def test_sorts_k_by_drawn_at() -> None:
    findings = QTcElectrolyteBridge().check(
        medications=_meds("Amiodarone"),
        labs=[
            {"name": "potassium", "value": 3.3, "drawn_at": "2026-01-05"},
            {"name": "potassium", "value": 4.1, "drawn_at": "2026-01-01"},
        ],
    )
    falling = next(f for f in findings if f.finding_kind == "falling_k_on_qt_agent")
    assert falling.k_values == [4.1, 3.3]


def test_no_qt_agents_no_findings() -> None:
    assert (
        QTcElectrolyteBridge().check(
            medications=_meds("Metformin"),
            labs=[{"name": "potassium", "value": 3.0, "drawn_at": "t"}],
        )
        == []
    )


def test_qt_agents_without_adverse_labs_no_findings() -> None:
    assert (
        QTcElectrolyteBridge().check(
            medications=_meds("Azithromycin"),
            labs=[{"name": "potassium", "value": 4.0, "drawn_at": "t"}],
        )
        == []
    )


def test_whole_token_matching() -> None:
    findings = QTcElectrolyteBridge().check(
        medications=_meds("Pseudoondansetron", "Haloperidolx"),
        labs=[
            {"name": "potassium", "value": 4.0, "drawn_at": "1"},
            {"name": "potassium", "value": 3.0, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Azithromycin", "Haloperidol"),
        labs=[
            {"name": "potassium", "value": 4.0, "drawn_at": "d1"},
            {"name": "potassium", "value": 3.2, "drawn_at": "d2"},
            {"name": "magnesium", "value": 2.0, "drawn_at": "d1"},
            {"name": "magnesium", "value": 1.5, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
    assert all("Never modifies medications" in f.rationale for f in findings)
