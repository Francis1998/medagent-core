"""Tests for hypoglycemia risk bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import HypoglycemiaRiskBridge as ExportedBridge
from medagent.safety.hypoglycemia_risk_bridge import HypoglycemiaRiskBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_falling_glucose_on_insulin() -> None:
    labs = [
        {"name": "glucose", "value": 140, "unit": "mg/dL", "drawn_at": "2026-01-01T08:00:00Z"},
        {"name": "glucose", "value": 65, "unit": "mg/dL", "drawn_at": "2026-01-01T12:00:00Z"},
    ]
    findings = HypoglycemiaRiskBridge().check(
        medications=_meds("Insulin glargine"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "falling_glucose_on_insulin")
    assert hit.severity is Severity.CRITICAL
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale


def test_falling_glucose_on_sulfonylurea() -> None:
    labs = [
        {"name": "blood glucose", "value": 160, "drawn_at": "a"},
        {"name": "blood glucose", "value": 90, "drawn_at": "b"},
    ]
    findings = HypoglycemiaRiskBridge().check(
        medications=_meds("Glipizide"),
        labs=labs,
    )
    assert any(f.finding_kind == "falling_glucose_on_sulfonylurea" for f in findings)


def test_low_glucose_on_agent() -> None:
    labs = [{"name": "glucose", "value": 55, "drawn_at": "t1"}]
    findings = HypoglycemiaRiskBridge().check(medications=_meds("Glyburide"), labs=labs)
    hit = next(f for f in findings if f.finding_kind == "low_glucose_on_hypoglycemic_agent")
    assert hit.severity is Severity.CRITICAL
    assert "Never modifies medications" in hit.rationale


def test_multi_agent_stack() -> None:
    findings = HypoglycemiaRiskBridge().check(
        medications=_meds("Insulin lispro", "Glimepiride"),
        labs=None,
    )
    stack = next(f for f in findings if f.finding_kind == "multi_hypoglycemic_agent_stack")
    assert stack.severity is Severity.HIGH
    assert "Never modifies medications" in stack.rationale


def test_sorts_glucose_by_drawn_at() -> None:
    findings = HypoglycemiaRiskBridge().check(
        medications=_meds("Insulin"),
        labs=[
            {"name": "glucose", "value": 70, "unit": "mg/dL", "drawn_at": "2026-01-05"},
            {"name": "glucose", "value": 130, "unit": "mg/dL", "drawn_at": "2026-01-01"},
        ],
    )
    falling = next(f for f in findings if f.finding_kind == "falling_glucose_on_insulin")
    assert falling.glucose_values == [130.0, 70.0]


def test_no_agents_no_findings() -> None:
    assert HypoglycemiaRiskBridge().check(medications=_meds("Metformin"), labs=[]) == []


def test_whole_token_matching() -> None:
    findings = HypoglycemiaRiskBridge().check(
        medications=_meds("Pseudoinsulin", "Glipizidex"),
        labs=[
            {"name": "glucose", "value": 140, "drawn_at": "1"},
            {"name": "glucose", "value": 60, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Humalog", "Glipizide"),
        labs=[
            {"name": "glucose", "value": 150, "drawn_at": "d1"},
            {"name": "glucose", "value": 80, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("RESEARCH USE ONLY" in f.rationale for f in findings)
    assert all("Never modifies medications" in f.rationale for f in findings)
