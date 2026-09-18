"""Tests for heparin/LMWH + serial anti-Xa monitoring trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import HeparinAntiXaTrendBridge as ExportedBridge
from medagent.safety.heparin_antixa_trend_bridge import HeparinAntiXaTrendBridge
from medagent.safety.heparin_platelet_trend_bridge import HeparinPlateletTrendBridge


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_antixa_on_heparin() -> None:
    labs = [
        {"name": "anti-xa", "value": 0.5, "drawn_at": "2026-01-01"},
        {"name": "anti-xa", "value": 1.2, "drawn_at": "2026-01-03"},
    ]
    findings = HeparinAntiXaTrendBridge().check(
        medications=_meds("Heparin infusion"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_antixa_on_heparin")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.antixa_values == [0.5, 1.2]


def test_supratherapeutic_antixa_on_lmwh() -> None:
    labs = [
        {"name": "anti xa level", "value": 0.8, "drawn_at": "a"},
        {"name": "anti xa level", "value": 1.8, "drawn_at": "b"},
    ]
    findings = HeparinAntiXaTrendBridge().check(
        medications=_meds("Enoxaparin"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "supratherapeutic_antixa_on_heparin")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_antixa == 1.8


def test_subtherapeutic_antixa() -> None:
    labs = [
        {"name": "factor xa activity", "value": 0.7, "drawn_at": "1"},
        {"name": "factor xa activity", "value": 0.15, "drawn_at": "2"},
    ]
    findings = HeparinAntiXaTrendBridge().check(
        medications=_meds("Dalteparin"),
        labs=labs,
    )
    assert any(f.finding_kind == "subtherapeutic_antixa_on_heparin" for f in findings)


def test_monitoring_advisory() -> None:
    labs = [
        {"name": "anti-xa", "value": 0.4, "drawn_at": "1"},
        {"name": "anti-xa", "value": 1.1, "drawn_at": "2"},
    ]
    findings = HeparinAntiXaTrendBridge().check(
        medications=_meds("Tinzaparin"),
        labs=labs,
    )
    assert any(f.finding_kind == "heparin_antixa_monitoring_advisory" for f in findings)


def test_no_agents_no_findings() -> None:
    labs = [
        {"name": "anti-xa", "value": 0.5, "drawn_at": "1"},
        {"name": "anti-xa", "value": 1.8, "drawn_at": "2"},
    ]
    assert HeparinAntiXaTrendBridge().check(medications=_meds("Warfarin"), labs=labs) == []


def test_agents_stable_antixa_no_findings() -> None:
    labs = [
        {"name": "anti-xa", "value": 0.6, "drawn_at": "1"},
        {"name": "anti-xa", "value": 0.65, "drawn_at": "2"},
    ]
    findings = HeparinAntiXaTrendBridge().check(
        medications=_meds("Heparin"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = HeparinAntiXaTrendBridge().check(
        medications=_meds("Heparin"),
        labs=[
            {"name": "anti-xa", "value": 1.3, "drawn_at": "2026-01-05"},
            {"name": "anti-xa", "value": 0.5, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_antixa_on_heparin")
    assert hit.antixa_values == [0.5, 1.3]


def test_distinct_from_platelet_bridge() -> None:
    assert HeparinAntiXaTrendBridge is not HeparinPlateletTrendBridge
    meds = _meds("Heparin", "Enoxaparin")
    labs = [
        {"name": "anti-xa", "value": 0.5, "drawn_at": "a"},
        {"name": "anti-xa", "value": 1.4, "drawn_at": "b"},
    ]
    assert HeparinAntiXaTrendBridge().check(medications=meds, labs=labs)
    plt_labs = [
        {"name": "platelets", "value": 220, "drawn_at": "a"},
        {"name": "platelets", "value": 90, "drawn_at": "b"},
    ]
    assert HeparinPlateletTrendBridge().check(medications=meds, labs=plt_labs)


def test_whole_token_matching() -> None:
    findings = HeparinAntiXaTrendBridge().check(
        medications=_meds("Pseudoheparin", "Enoxaparinx"),
        labs=[
            {"name": "anti-xa", "value": 0.5, "drawn_at": "1"},
            {"name": "anti-xa", "value": 1.8, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Heparin", "Enoxaparin")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "anti-xa", "value": 0.5, "drawn_at": "d1"},
        {"name": "anti-xa", "value": 1.6, "drawn_at": "d2"},
    ]
    findings = HeparinAntiXaTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Nadroparin"),
        labs=[
            {"name": "heparin anti-xa", "value": 0.5, "drawn_at": "d1"},
            {"name": "heparin anti-xa", "value": 1.2, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
