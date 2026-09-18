"""Tests for valproate + serial ammonia hyperammonemia trend bridge."""

from __future__ import annotations

from medagent.models import Medication, Severity
from medagent.safety import ValproateAmmoniaTrendBridge as ExportedBridge
from medagent.safety.lamotrigine_valproate_checker import LamotrigineValproateChecker
from medagent.safety.valproate_ammonia_trend_bridge import ValproateAmmoniaTrendBridge
from medagent.safety.valproate_carbapenem_checker import ValproateCarbapenemChecker


def _meds(*names: str) -> list[Medication]:
    return [Medication(name=name) for name in names]


def test_rising_ammonia_on_valproate() -> None:
    labs = [
        {"name": "ammonia", "value": 35, "drawn_at": "2026-01-01"},
        {"name": "ammonia", "value": 95, "drawn_at": "2026-01-08"},
    ]
    findings = ValproateAmmoniaTrendBridge().check(
        medications=_meds("Depakote 500 mg"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "rising_ammonia_on_valproate")
    assert hit.severity in {Severity.HIGH, Severity.CRITICAL}
    assert "RESEARCH USE ONLY" in hit.rationale
    assert "Never modifies medications" in hit.rationale
    assert hit.ammonia_values == [35.0, 95.0]


def test_critical_ammonia_on_valproate() -> None:
    labs = [
        {"name": "serum ammonia", "value": 60, "drawn_at": "a"},
        {"name": "serum ammonia", "value": 140, "drawn_at": "b"},
    ]
    findings = ValproateAmmoniaTrendBridge().check(
        medications=_meds("Divalproex"),
        labs=labs,
    )
    hit = next(f for f in findings if f.finding_kind == "critical_ammonia_on_valproate")
    assert hit.severity is Severity.CRITICAL
    assert hit.latest_ammonia == 140.0


def test_elevated_ammonia_on_valproate() -> None:
    labs = [
        {"name": "plasma ammonia", "value": 40, "drawn_at": "1"},
        {"name": "plasma ammonia", "value": 70, "drawn_at": "2"},
    ]
    findings = ValproateAmmoniaTrendBridge().check(
        medications=_meds("Valproic acid"),
        labs=labs,
    )
    assert any(f.finding_kind == "elevated_ammonia_on_valproate" for f in findings)


def test_hyperammonemia_advisory() -> None:
    labs = [
        {"name": "ammonia level", "value": 30, "drawn_at": "1"},
        {"name": "ammonia level", "value": 80, "drawn_at": "2"},
    ]
    findings = ValproateAmmoniaTrendBridge().check(
        medications=_meds("Depakene"),
        labs=labs,
    )
    assert any(f.finding_kind == "valproate_hyperammonemia_advisory" for f in findings)


def test_no_valproate_no_findings() -> None:
    labs = [
        {"name": "ammonia", "value": 30, "drawn_at": "1"},
        {"name": "ammonia", "value": 120, "drawn_at": "2"},
    ]
    assert ValproateAmmoniaTrendBridge().check(medications=_meds("Levetiracetam"), labs=labs) == []


def test_valproate_stable_ammonia_no_findings() -> None:
    labs = [
        {"name": "ammonia", "value": 30, "drawn_at": "1"},
        {"name": "ammonia", "value": 32, "drawn_at": "2"},
    ]
    findings = ValproateAmmoniaTrendBridge().check(
        medications=_meds("Valproate"),
        labs=labs,
    )
    assert findings == []


def test_sorts_by_drawn_at() -> None:
    findings = ValproateAmmoniaTrendBridge().check(
        medications=_meds("Valproate"),
        labs=[
            {"name": "ammonia", "value": 90, "drawn_at": "2026-01-05"},
            {"name": "ammonia", "value": 30, "drawn_at": "2026-01-01"},
        ],
    )
    hit = next(f for f in findings if f.finding_kind == "rising_ammonia_on_valproate")
    assert hit.ammonia_values == [30.0, 90.0]


def test_distinct_from_carbapenem_and_lamotrigine() -> None:
    assert ValproateAmmoniaTrendBridge is not ValproateCarbapenemChecker
    assert ValproateAmmoniaTrendBridge is not LamotrigineValproateChecker
    meds = _meds("Valproate", "Meropenem", "Lamotrigine")
    labs = [
        {"name": "ammonia", "value": 35, "drawn_at": "a"},
        {"name": "ammonia", "value": 90, "drawn_at": "b"},
    ]
    assert ValproateAmmoniaTrendBridge().check(medications=meds, labs=labs)
    assert ValproateCarbapenemChecker().check(meds)
    assert LamotrigineValproateChecker().check(meds)


def test_whole_token_matching() -> None:
    findings = ValproateAmmoniaTrendBridge().check(
        medications=_meds("Pseudovalproate"),
        labs=[
            {"name": "ammonia", "value": 30, "drawn_at": "1"},
            {"name": "ammonia", "value": 120, "drawn_at": "2"},
        ],
    )
    assert findings == []


def test_never_modifies_medications() -> None:
    meds = _meds("Depakote", "Divalproex")
    snapshot = [(m.name, m.model_dump()) for m in meds]
    labs = [
        {"name": "ammonia", "value": 40, "drawn_at": "d1"},
        {"name": "ammonia", "value": 110, "drawn_at": "d2"},
    ]
    findings = ValproateAmmoniaTrendBridge().check(medications=meds, labs=labs)
    assert findings
    assert [(m.name, m.model_dump()) for m in meds] == snapshot


def test_exported() -> None:
    findings = ExportedBridge().check(
        medications=_meds("Valproate"),
        labs=[
            {"name": "nh3", "value": 40, "drawn_at": "d1"},
            {"name": "nh3", "value": 85, "drawn_at": "d2"},
        ],
    )
    assert findings
    assert all("Never modifies medications" in f.rationale for f in findings)
